"""Background search grounding using Google Gemini Search Grounding."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import re
import time
from html import unescape
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

import httpx

log = logging.getLogger(__name__)

# Upstream models from JARVIS-OMA. Gemini 2.5 uses a separate grounding allowance,
# allowing it to function even if the shared Gemini 3.x allowance fails.
GROUNDING_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
)

_search_key_cooldown: dict[str, float] = {}


class SearchProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def get_key_cooldown(key: str) -> float:
    return _search_key_cooldown.get(key, 0.0)


def set_key_cooldown(key: str, cooldown_seconds: float = 300.0) -> None:
    _search_key_cooldown[key] = time.monotonic() + cooldown_seconds


def clear_cooldowns() -> None:
    _search_key_cooldown.clear()


def _public_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except Exception:
        return False
    if parsed.scheme not in ("https", "http") or not hostname or parsed.username:
        return False
    host = hostname.rstrip(".").casefold()
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return address.is_global


def _clean_text(text: str, max_chars: int = 4000) -> str:
    cleaned = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()
    return cleaned[:max_chars]


async def _get_json(url: str, *, headers: dict[str, str], timeout: float = 9.0) -> dict:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        # Prevent unmocked network calls during tests
        raise SearchProviderError("unmocked network call prohibited during test", retryable=False)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream("GET", url, headers=headers) as response:
                status = response.status_code
                if status == 429:
                    raise SearchProviderError("search provider quota is exhausted")
                if status in (401, 403):
                    raise SearchProviderError("search provider credentials were rejected", retryable=False)
                if status >= 400:
                    raise SearchProviderError("search provider is unavailable")
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > 1_000_000:
                        raise SearchProviderError("search provider returned too much data")
    except httpx.TimeoutException:
        raise SearchProviderError("search provider timed out or is unreachable") from None
    except httpx.RequestError:
        raise SearchProviderError("search provider timed out or is unreachable") from None
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        raise SearchProviderError("search provider returned invalid data") from None
    if not isinstance(data, dict):
        raise SearchProviderError("search provider returned invalid data")
    return data


def brave_available(api_key: str | None = None) -> bool:
    key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY")
    return bool(key)


async def brave_search(query: str, *, api_key: str | None = None) -> dict[str, Any]:
    """Search using Brave's Web Search API."""
    key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY")
    if not key:
        raise SearchProviderError("Brave Search API key is not configured", retryable=False)
    url = "https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": query, "count": 5})
    try:
        data = await asyncio.wait_for(
            _get_json(url, headers={"Accept": "application/json", "X-Subscription-Token": key}),
            timeout=11.0,
        )
    except TimeoutError:
        raise SearchProviderError("Brave Search timed out") from None
    results = []
    seen = set()
    for item in (data.get("web") or {}).get("results") or []:
        if not isinstance(item, dict) or not _public_url(item.get("url")):
            continue
        url_val = item["url"]
        if url_val in seen:
            continue
        seen.add(url_val)
        results.append({
            "title": _clean_text(str(item.get("title") or url_val), 200),
            "url": url_val,
            "snippet": _clean_text(str(item.get("description") or ""), 500),
        })
        if len(results) == 5:
            break
    if not results:
        raise SearchProviderError("Brave Search returned no usable results")
    return {
        "ok": True,
        "answer": f"Search results for: {query[:200]}",
        "sources": results,
        "search_queries": [query],
        "provider": "Brave Search",
        "model": "brave",
    }


_TIME_SENSITIVE = re.compile(
    r"\b(today|tonight|tomorrow|yesterday|latest|current|currently|recent|now|news|"
    r"price|stock|share|market|weather|forecast|score|schedule|election|president|"
    r"ceo|exchange rate|live|20[0-9][0-9])\b",
    re.IGNORECASE,
)


def encyclopedia_eligible(query: str) -> bool:
    """Wikipedia is useful for stable background, never for live/current facts."""
    return not bool(_TIME_SENSITIVE.search(query))


async def wikipedia_search(query: str) -> dict[str, Any]:
    """Search Wikimedia's public REST API for stable encyclopedic background."""
    if not encyclopedia_eligible(query):
        raise SearchProviderError("Wikipedia cannot verify current information", retryable=False)
    url = "https://en.wikipedia.org/w/rest.php/v1/search/page?" + urlencode({"q": query, "limit": 5})
    try:
        data = await asyncio.wait_for(
            _get_json(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "JARVIS-OS/1.0 (local voice assistant)",
                },
            ),
            timeout=11.0,
        )
    except TimeoutError:
        raise SearchProviderError("Wikipedia search timed out") from None
    results = []
    snippets = []
    for page in data.get("pages") or []:
        if not isinstance(page, dict) or not isinstance(page.get("key"), str):
            continue
        title = _clean_text(str(page.get("title") or page["key"]), 200)
        desc = _clean_text(str(page.get("description") or page.get("excerpt") or ""), 500)
        link = "https://en.wikipedia.org/wiki/" + quote(page["key"], safe="")
        if desc:
            snippets.append(f"{title}: {desc}")
        else:
            snippets.append(title)
        results.append({"title": title, "url": link, "snippet": desc})
        if len(results) == 5:
            break
    if not results:
        raise SearchProviderError("Wikipedia returned no relevant pages")
    answer = "\n\n".join(snippets) if snippets else f"Encyclopedia background for: {query[:200]}"
    return {
        "ok": True,
        "answer": answer,
        "sources": results,
        "search_queries": [query],
        "provider": "Wikipedia",
        "model": "wikipedia",
    }


async def duckduckgo_lite_search(query: str) -> dict[str, Any]:
    """Search DuckDuckGo Lite for live web results when API quota is exhausted."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise SearchProviderError("unmocked network call prohibited during test", retryable=False)
    url = "https://lite.duckduckgo.com/lite/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urlencode({"q": query})
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.post(url, content=data, headers=headers)
            if resp.status_code != 200:
                raise SearchProviderError(f"DuckDuckGo returned status {resp.status_code}")
            html = resp.text
    except Exception as exc:
        raise SearchProviderError(f"DuckDuckGo search failed: {exc}") from exc

    links = re.findall(r'<a[^>]*href=[\'"]([^\'"]+)[\'"][^>]*class=[\'"]result-link[\'"][^>]*>(.*?)</a>', html)
    snippets = re.findall(r'<td[^>]*class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', html, re.DOTALL)

    results = []
    answers = []
    seen = set()
    for i in range(min(len(links), len(snippets))):
        u, t = links[i]
        s = _clean_text(snippets[i], 500)
        t = _clean_text(t, 200)
        if not u or not _public_url(u) or u in seen:
            continue
        seen.add(u)
        results.append({"title": t, "url": u, "snippet": s})
        answers.append(f"{t}: {s}")
        if len(results) >= 5:
            break

    if not results:
        raise SearchProviderError("DuckDuckGo returned no usable results")

    return {
        "ok": True,
        "answer": "\n\n".join(answers),
        "sources": results,
        "search_queries": [query],
        "provider": "DuckDuckGo Search",
        "model": "duckduckgo-lite",
    }


async def fallback_background_search(query: str, error: str = "") -> dict[str, Any]:
    """Lightweight background web search using Brave Search, DuckDuckGo Lite, or Wikipedia REST API."""
    if brave_available():
        try:
            return await brave_search(query)
        except SearchProviderError as exc:
            log.warning("Brave Search fallback unavailable: %s", exc)

    try:
        return await duckduckgo_lite_search(query)
    except Exception as exc:
        log.warning("DuckDuckGo Lite fallback unavailable: %s", exc)

    if encyclopedia_eligible(query):
        try:
            return await wikipedia_search(query)
        except SearchProviderError as exc:
            log.warning("Wikipedia fallback unavailable: %s", exc)

    note = "Google search quota cooling down" if ("429" in error or "RESOURCE_EXHAUSTED" in error) else (error[:100] if error else "")
    return {
        "ok": False,
        "answer": "Background grounding temporarily unavailable.",
        "sources": [],
        "search_queries": [query],
        "provider": "None",
        "model": "none",
        "note": note,
    }


async def background_google_grounding(
    query: str,
    *,
    api_key: str | None = None,
    timeout: float = 12.0,
) -> dict[str, Any]:
    """Execute background grounding using Google Search via Gemini API, with fallbacks.

    Returns a structured dictionary with 'ok', 'answer', 'sources', 'provider', and 'model'.
    Falls back to Brave Search or Wikipedia REST API if the API key is exhausted or unavailable.
    """
    configured_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not configured_key:
        return await fallback_background_search(query, error="No GEMINI_API_KEY configured")

    keys = [configured_key] if isinstance(configured_key, str) else list(configured_key)
    for k in ('GEMINI_API_KEY_1', 'GEMINI_API_KEY_4', 'GEMINI_API_KEY_3', 'GEMINI_API_KEY_5'):
        val = os.environ.get(k)
        if val and val not in keys:
            keys.append(val)
    deadline = time.monotonic() + timeout
    last_error = ""

    from google import genai
    from google.genai import types

    for key in keys:
        if time.monotonic() >= deadline:
            last_error = "Grounding timed out"
            break
        if _search_key_cooldown.get(key, 0.0) > time.monotonic():
            last_error = "Google search quota cooling down"
            continue

        skip_key = False
        for model in GROUNDING_MODELS:
            remaining = deadline - time.monotonic()
            if remaining <= 1.0:
                last_error = "Grounding timed out"
                break

            try:
                async with genai.Client(api_key=key).aio as client:
                    res = await asyncio.wait_for(
                        client.models.generate_content(
                            model=model,
                            contents=query,
                            config=types.GenerateContentConfig(
                                tools=[types.Tool(google_search=types.GoogleSearch())],
                                temperature=0.0,
                                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                            ),
                        ),
                        timeout=min(remaining, 8.0),
                    )

                answer = _clean_text(getattr(res, "text", "") or "")
                candidates = getattr(res, "candidates", []) or []
                grounding = (
                    getattr(candidates[0], "grounding_metadata", None)
                    if candidates
                    else None
                )

                sources: list[dict[str, str]] = []
                seen_urls = set()
                for chunk in getattr(grounding, "grounding_chunks", []) or []:
                    web = getattr(chunk, "web", None)
                    uri = getattr(web, "uri", None)
                    title = getattr(web, "title", "") or uri or "Source"
                    if uri and _public_url(uri) and uri not in seen_urls:
                        seen_urls.add(uri)
                        sources.append({"title": _clean_text(title, 120), "url": uri})
                    if len(sources) >= 5:
                        break

                search_queries = list(getattr(grounding, "web_search_queries", []) or [])

                if answer:
                    return {
                        "ok": True,
                        "answer": answer,
                        "sources": sources,
                        "search_queries": search_queries,
                        "provider": "Google Search Grounding",
                        "model": model,
                    }
            except TimeoutError:
                last_error = "Grounding timed out"
                skip_key = True
                break
            except Exception as exc:
                err_msg = str(exc)
                last_error = err_msg
                code = getattr(exc, "code", getattr(exc, "status_code", None))
                if code == 429 or "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    log.info("Grounding quota exhausted for %s, cooling down key for 300s", model)
                    set_key_cooldown(key, 300.0)
                    skip_key = True
                    break
                elif code in (401, 403) or "401" in err_msg or "403" in err_msg or "UNAUTHENTICATED" in err_msg or "PERMISSION_DENIED" in err_msg:
                    log.warning("Grounding credentials rejected for key, cooling down for 300s")
                    set_key_cooldown(key, 300.0)
                    skip_key = True
                    break
                elif code in (400, 404) or "404" in err_msg or "NOT_FOUND" in err_msg:
                    log.info("Model %s unavailable, trying next model", model)
                    continue
                log.warning("Grounding failed on %s: %s", model, exc)
                skip_key = True
                break

        if skip_key:
            continue

    return await fallback_background_search(query, error=last_error)


def format_grounding_result(res: dict[str, Any]) -> str:
    """Format structured grounding result as a clean text response for tools."""
    lines = [res.get("answer", "")]
    sources = res.get("sources", [])
    if sources:
        lines.append("\nSources:")
        for s in sources:
            lines.append(f"- {s.get('title', 'Link')}: {s.get('url', '')}")
    if res.get("note"):
        lines.append(f"\n[{res['note']}]")
    return "\n".join(lines).strip()
