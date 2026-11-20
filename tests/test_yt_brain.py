import json
import sqlite3
import sys
import types

import pytest

from connectors.yt_brain import MAX_NOTE_CHARS, YtBrainClient
from jarvis_control.config import Config
from jarvis_control.skills import ControlSkills, UnifiedSkills
from skills.skills import DesktopSkills
from voice_layer.daemon import build_instruction


@pytest.fixture
def yt_client(tmp_path):
    db_path = tmp_path / "yt?brain#fixture.sqlite"
    note_path = tmp_path / "fixture-note.md"
    note_path.write_text("fixture note about AI", encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE notes (
                title TEXT, url TEXT, watched TEXT, path TEXT, video_id TEXT,
                topic TEXT
            );
            CREATE VIRTUAL TABLE notes_fts USING fts5(video_id, title, content);
        """)
        conn.execute(
            "INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?)",
            ("Fixture AI", "https://example.invalid/video", "2026-11-16", str(note_path), "fixture-id", "AI"),
        )
        conn.execute("INSERT INTO notes_fts VALUES (?, ?, ?)", ("fixture-id", "Fixture AI", "AI fixture searchable content"))
    return YtBrainClient(socket_path=tmp_path / "unused-bus.sock", kb_path=db_path)


@pytest.mark.asyncio
async def test_yt_brain_declarations_and_routing(monkeypatch, yt_client):
    monkeypatch.setattr("skills.domains.yt_brain.get_client", lambda: yt_client)
    desktop = DesktopSkills()
    control = ControlSkills(Config())
    skills = UnifiedSkills(control_skills=control, desktop_skills=desktop)
    try:
        live_names = {tool["name"] for tool in skills.live_declarations}
        assert {"yt_brain_search", "yt_brain_topics", "yt_brain_status", "yt_brain_get"} <= live_names

        instruction = build_instruction([{"function_declarations": skills.live_declarations}])
        assert "YOUTUBE KNOWLEDGE BRAIN" in instruction
        assert "yt_brain_search" in instruction

        status = json.loads(await skills.execute("yt_brain_status", {}))
        assert status["ok"] is True
        assert status["total_notes"] == 1
        assert status["status"] == "archive_available"
        assert status["worker_reachable"] is False

        topics = json.loads(await skills.execute("yt_brain_topics", {}))
        assert topics["ok"] is True
        assert topics["topics"] == {"AI": 1}

        search = json.loads(await skills.execute("yt_brain_search", {"query": "AI", "limit": 2}))
        assert search["ok"] is True
        assert [result["video_id"] for result in search["results"]] == ["fixture-id"]

        note = json.loads(await skills.execute("yt_brain_get", {"video_id": "fixture-id"}))
        assert note["ok"] is True
        assert note["content"] == "fixture note about AI"
    finally:
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_direct_search_bounds_results_and_accepts_uri_special_chars(yt_client):
    result = await yt_client.search("AI", limit=10_000)
    assert result["ok"] is True
    assert len(result["results"]) == 1

    invalid = await yt_client.search("AI", limit=0)
    assert invalid["ok"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("topic", ["yt-brain.search", "yt-brain.get", "yt-brain.topics"])
async def test_bus_errors_are_not_reported_as_success(topic, tmp_path):
    class FailingBusClient(YtBrainClient):
        async def _bus_request(self, requested_topic, payload, timeout=3.0):
            assert requested_topic == topic
            return {"ok": False, "error": "bus operation failed"}

    client = FailingBusClient(socket_path=tmp_path / "unused", kb_path=tmp_path / "missing.sqlite")
    if topic.endswith("search"):
        result = await client.search("AI")
    elif topic.endswith("get"):
        result = await client.get(video_id="missing")
    else:
        result = await client.topics()
    assert result == {"ok": False, "error": "bus operation failed"}


@pytest.mark.asyncio
async def test_bus_get_without_note_metadata_is_not_success(tmp_path):
    class MissingNoteBusClient(YtBrainClient):
        async def _bus_request(self, topic, payload, timeout=3.0):
            return {"ok": True, "content": "", "meta": {}}

    client = MissingNoteBusClient(socket_path=tmp_path / "unused", kb_path=tmp_path / "missing.sqlite")
    assert await client.get(video_id="missing") == {"ok": False, "error": "Note not found"}


@pytest.mark.asyncio
async def test_get_truncates_oversized_note_content(yt_client, tmp_path):
    large_note = tmp_path / "large.md"
    large_note.write_text("x" * (MAX_NOTE_CHARS + 100), encoding="utf-8")
    with sqlite3.connect(yt_client.kb_path) as conn:
        conn.execute("UPDATE notes SET path = ?", (str(large_note),))

    result = yt_client._direct_get(video_id="fixture-id")
    assert result["ok"] is True
    assert len(result["content"]) < MAX_NOTE_CHARS + 100
    assert result["content"].endswith("[Content truncated]")


def test_get_reports_missing_note_file(yt_client):
    with sqlite3.connect(yt_client.kb_path) as conn:
        conn.execute("UPDATE notes SET path = ?", (str(yt_client.kb_path.parent / "missing.md"),))
    assert yt_client._direct_get(video_id="fixture-id") == {"ok": False, "error": "Note file not found"}


@pytest.mark.asyncio
async def test_parallel_bus_requests_register_distinct_client_ids(monkeypatch, yt_client):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    bus = MagicMock()
    bus.return_value.__aenter__.return_value.request = AsyncMock(
        return_value=types.SimpleNamespace(type="reply", payload={"status": "online"}))
    monkeypatch.setitem(sys.modules, "core_engine", types.SimpleNamespace(AgentBusClient=bus))
    yt_client.socket_path.touch()
    first, second = await asyncio.gather(yt_client.status(), yt_client.status())
    assert all(result["ok"] and result["worker_reachable"] for result in (first, second))
    assert len({call.kwargs["agent_id"] for call in bus.call_args_list}) == 2


@pytest.mark.asyncio
async def test_bus_connection_setup_is_bounded(monkeypatch, tmp_path):
    class StalledBusClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            import asyncio
            await asyncio.sleep(10)

        async def __aexit__(self, *args):
            pass

    core_engine = types.ModuleType("core_engine")
    core_engine.AgentBusClient = StalledBusClient
    monkeypatch.setitem(sys.modules, "core_engine", core_engine)
    socket_path = tmp_path / "agent_bus.sock"
    socket_path.touch()
    client = YtBrainClient(socket_path=socket_path, kb_path=tmp_path / "unused.sqlite")
    assert await client._bus_request("yt-brain.status", {}, timeout=0.01) is None


@pytest.mark.asyncio
async def test_search_caps_limit_before_bus_request(monkeypatch, yt_client):
    from connectors.yt_brain import MAX_SEARCH_RESULTS
    from unittest.mock import AsyncMock
    request = AsyncMock(return_value={'results': []})
    monkeypatch.setattr(yt_client, '_bus_request', request)
    await yt_client.search('AI', limit=10000)
    request.assert_awaited_once_with('yt-brain.search', {'query': 'AI', 'limit': MAX_SEARCH_RESULTS})
