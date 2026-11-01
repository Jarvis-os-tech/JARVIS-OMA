"""Tests for background Google Search Grounding in jarvis_control."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jarvis_control.grounding import (
    background_google_grounding,
    fallback_background_search,
    format_grounding_result,
    _public_url,
    _clean_text,
    _get_json,
    SearchProviderError,
    get_key_cooldown,
    clear_cooldowns,
    encyclopedia_eligible,
    GROUNDING_MODELS,
)
from jarvis_control.tools import Executor, Result
from jarvis_control.config import Config


def test_public_url_validation():
    assert _public_url("https://python.org") is True
    assert _public_url("http://example.com/page?q=1") is True
    assert _public_url("ftp://not-http.com") is False
    assert _public_url("http://") is False
    assert _public_url("not a url") is False
    assert _public_url("http://localhost:8080") is False
    assert _public_url("http://127.0.0.1") is False


def test_clean_text():
    assert _clean_text("Hello &amp; world\n\n  test  ") == "Hello & world test"
    assert len(_clean_text("a" * 5000, max_chars=100)) == 100


def test_format_grounding_result():
    res = {
        "ok": True,
        "answer": "Python 3.14 is the latest version.",
        "sources": [{"title": "Python.org", "url": "https://python.org"}],
        "search_queries": ["python version"],
        "provider": "Google Search Grounding",
        "note": "Sample note",
    }
    formatted = format_grounding_result(res)
    assert "Python 3.14" in formatted
    assert "Sources:" in formatted
    assert "- Python.org: https://python.org" in formatted
    assert "[Sample note]" in formatted


def test_grounding_models_exact_tuple():
    assert GROUNDING_MODELS == (
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-2.5-flash",
    )


@pytest.mark.asyncio
async def test_google_grounding_success_mock():
    mock_candidate = MagicMock()
    mock_candidate.grounding_metadata = MagicMock(
        web_search_queries=["latest python version"],
        grounding_chunks=[
            MagicMock(web=MagicMock(uri="https://www.python.org/downloads/", title="Python Downloads"))
        ],
    )
    mock_res = MagicMock(
        text="Python 3.14.0 is available.",
        candidates=[mock_candidate],
    )

    fake_client = MagicMock()
    fake_client.models.generate_content = AsyncMock(return_value=mock_res)
    fake_client_ctx = MagicMock()
    fake_client_ctx.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("google.genai.Client") as mock_genai:
        mock_genai.return_value.aio = fake_client_ctx
        res = await background_google_grounding("latest python version", api_key="fake-key")

    assert res["ok"] is True
    assert "Python 3.14.0" in res["answer"]
    assert len(res["sources"]) == 1
    assert res["sources"][0]["url"] == "https://www.python.org/downloads/"
    assert res["provider"] == "Google Search Grounding"


@pytest.mark.asyncio
async def test_web_search_tool_uses_background_grounding():
    executor = Executor(Config())
    with patch("jarvis_control.grounding.background_google_grounding", new_callable=AsyncMock) as mock_ground:
        mock_ground.return_value = {
            "ok": True,
            "answer": "Grounded answer from Google.",
            "sources": [{"title": "Source 1", "url": "https://example.com"}],
            "provider": "Google Search Grounding",
        }
        res = executor.call("web_search", {"query": "test query", "background": True})
        assert res.ok is True
        assert "Grounded answer from Google" in res.output
        assert "https://example.com" in res.output
        mock_ground.assert_awaited_once_with("test query")


@pytest.mark.asyncio
async def test_quota_exhaustion_cools_down_key():
    clear_cooldowns()

    fake_client = MagicMock()
    error_429 = Exception("Resource exhausted (status 429)")
    error_429.code = 429
    fake_client.models.generate_content = AsyncMock(side_effect=error_429)
    fake_client_ctx = MagicMock()
    fake_client_ctx.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("google.genai.Client") as mock_genai:
        mock_genai.return_value.aio = fake_client_ctx
        res = await background_google_grounding("search query", api_key="quota-key")

    assert get_key_cooldown("quota-key") > 0
    assert res["ok"] is False


@pytest.mark.asyncio
async def test_invalid_key_cools_down():
    clear_cooldowns()

    fake_client = MagicMock()
    error_403 = Exception("Permission denied (status 403)")
    error_403.code = 403
    fake_client.models.generate_content = AsyncMock(side_effect=error_403)
    fake_client_ctx = MagicMock()
    fake_client_ctx.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("google.genai.Client") as mock_genai:
        mock_genai.return_value.aio = fake_client_ctx
        res = await background_google_grounding("search query", api_key="invalid-key")

    assert get_key_cooldown("invalid-key") > 0
    assert res["ok"] is False


@pytest.mark.asyncio
async def test_wikipedia_fallback_for_encyclopedic_query(monkeypatch):
    fake_wiki_json = {
        "pages": [
            {
                "key": "Ada_Lovelace",
                "title": "Ada Lovelace",
                "description": "English mathematician and first computer programmer",
            }
        ]
    }
    monkeypatch.setattr("jarvis_control.grounding._get_json", AsyncMock(return_value=fake_wiki_json))
    res = await fallback_background_search("Ada Lovelace history")
    assert res["ok"] is True
    assert "Ada Lovelace" in res["answer"]
    assert len(res["sources"]) == 1
    assert "https://en.wikipedia.org/wiki/Ada_Lovelace" in res["sources"][0]["url"]
    assert res["provider"] == "Wikipedia"


def test_wikipedia_rejects_time_sensitive_query():
    assert encyclopedia_eligible("history of ancient rome") is True
    assert encyclopedia_eligible("current weather in new york today") is False
    assert encyclopedia_eligible("latest stock price") is False
    assert encyclopedia_eligible("who is the president now") is False


@pytest.mark.asyncio
async def test_brave_search_fallback(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "fake-brave-key")
    fake_brave_json = {
        "web": {
            "results": [
                {
                    "title": "Brave Result",
                    "url": "https://example.com/brave",
                    "description": "Description of brave search result",
                }
            ]
        }
    }
    monkeypatch.setattr("jarvis_control.grounding._get_json", AsyncMock(return_value=fake_brave_json))
    res = await fallback_background_search("test query")
    assert res["ok"] is True
    assert "Brave Search" in res["provider"]
    assert res["sources"][0]["url"] == "https://example.com/brave"


@pytest.mark.asyncio
async def test_unmocked_network_calls_prohibited_during_test():
    with pytest.raises(SearchProviderError, match="prohibited during test"):
        await _get_json("https://en.wikipedia.org", headers={})


def test_background_failure_does_not_open_browser_window(monkeypatch):
    executor = Executor(Config())
    opened = []
    monkeypatch.setattr(executor, "_open_web_window", lambda *args, **kwargs: opened.append(args))

    with patch("jarvis_control.grounding.background_google_grounding", new_callable=AsyncMock) as mock_ground:
        mock_ground.return_value = {"ok": False, "answer": "Background grounding temporarily unavailable.", "sources": []}
        res = executor._tool_web_search("public info", background=True)
        assert res.ok is True
        assert "Background grounding temporarily unavailable" in res.output
        assert len(opened) == 0  # No browser window opened on desktop
