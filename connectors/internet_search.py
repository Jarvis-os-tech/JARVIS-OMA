"""Bounded, source-backed web search providers for the voice assistant."""
from __future__ import annotations

import asyncio
from html import unescape
import ipaddress
import json
import re
from urllib.parse import quote, urlencode, urlsplit
import httpx
from connectors import credentials

# All support Google Search grounding. Gemini 2.5 uses a separate grounding
# allowance, so it can still work after the shared Gemini 3.x allowance fails.
GROUNDING_MODELS = (
    'gemini-3.8-flash',
    'gemini-3.7-flash',
    'gemini-3.6-flash',
    'gemini-3.5-flash-lite',
    'gemini-2.5-flash',
)


class SearchProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def brave_available() -> bool:
    return bool(credentials.get('BRAVE_SEARCH_API_KEY'))


async def _get_json(url: str, *, headers: dict[str, str]) -> dict:
    try:
        async with httpx.AsyncClient(timeout=9, follow_redirects=False) as client:
            async with client.stream('GET', url, headers=headers) as response:
                status = response.status_code
                if status == 429:
                    raise SearchProviderError('search provider quota is exhausted')
                if status in (401, 403):
                    raise SearchProviderError('search provider credentials were rejected', retryable=False)
                if status >= 400:
                    raise SearchProviderError('search provider is unavailable')
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > 1_000_000:
                        raise SearchProviderError('search provider returned too much data')
    except httpx.TimeoutException:
        raise SearchProviderError('search provider timed out or is unreachable') from None
    except httpx.RequestError:
        raise SearchProviderError('search provider timed out or is unreachable') from None
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        raise SearchProviderError('search provider returned invalid data') from None
    if not isinstance(data, dict):
        raise SearchProviderError('search provider returned invalid data')
    return data


def _clean(value: str, limit: int) -> str:
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', value))).strip()[:limit]


def _public_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    parsed = urlsplit(value)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username:
        return False
    host = parsed.hostname.rstrip('.').casefold()
    if host == 'localhost' or host.endswith('.localhost'):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return address.is_global


async def brave_search(query: str, *, api_key: str | None = None) -> dict:
    """Use Brave's documented Web Search API when the user configured a key."""
    key = api_key if api_key is not None else credentials.get('BRAVE_SEARCH_API_KEY')
    if not key:
        raise SearchProviderError('Brave Search API key is not configured', retryable=False)
    url = 'https://api.search.brave.com/res/v1/web/search?' + urlencode({'q': query, 'count': 5})
    try:
        data = await asyncio.wait_for(_get_json(
            url, headers={'Accept': 'application/json',
                          'X-Subscription-Token': key}), timeout=11)
    except TimeoutError:
        raise SearchProviderError('Brave Search timed out') from None
    results = []
    seen = set()
    for item in (data.get('web') or {}).get('results') or []:
        if not isinstance(item, dict) or not _public_url(item.get('url')):
            continue
        url = item['url']
        if url in seen:
            continue
        seen.add(url)
        results.append({'title': _clean(str(item.get('title') or url), 200),
                        'url': url,
                        'snippet': _clean(str(item.get('description') or ''), 500)})
        if len(results) == 5:
            break
    if not results:
        raise SearchProviderError('Brave Search returned no usable results')
    return {'answer': 'Search results for: ' + query[:200], 'sources': results,
            'provider': 'Brave Search'}


_TIME_SENSITIVE = re.compile(
    r'\b(today|tonight|tomorrow|yesterday|latest|current|currently|recent|now|news|'
    r'price|stock|share|market|weather|forecast|score|schedule|election|president|'
    r'ceo|exchange rate|live|20[0-9][0-9])\b', re.IGNORECASE)


def encyclopedia_eligible(query: str) -> bool:
    """Wikipedia is useful for stable background, never for live/current facts."""
    return not _TIME_SENSITIVE.search(query)


async def wikipedia_search(query: str) -> dict:
    """Search Wikimedia's public REST API for stable encyclopedic background."""
    if not encyclopedia_eligible(query):
        raise SearchProviderError('Wikipedia cannot verify current information', retryable=False)
    url = 'https://en.wikipedia.org/w/rest.php/v1/search/page?' + urlencode({'q': query, 'limit': 5})
    try:
        data = await asyncio.wait_for(_get_json(
            url, headers={'Accept': 'application/json',
                          'User-Agent': 'Jarvis-OMA/1.0 (local voice assistant)'}), timeout=11)
    except TimeoutError:
        raise SearchProviderError('Wikipedia search timed out') from None
    results = []
    for page in data.get('pages') or []:
        if not isinstance(page, dict) or not isinstance(page.get('key'), str):
            continue
        title = _clean(str(page.get('title') or page['key']), 200)
        description = _clean(str(page.get('description') or page.get('excerpt') or ''), 500)
        results.append({'title': title,
                        'url': 'https://en.wikipedia.org/wiki/' + quote(page['key'], safe=''),
                        'snippet': description})
        if len(results) == 5:
            break
    if not results:
        raise SearchProviderError('Wikipedia returned no relevant pages')
    return {'answer': 'Encyclopedia background for: ' + query[:200],
            'sources': results, 'provider': 'Wikipedia'}
