"""Unit tests for AgentReachDomain in JARVIS OS."""
import pytest
from unittest.mock import AsyncMock, patch
from skills.domains.agent_reach import AgentReachDomain
from skills.errors import SkillError


class MockSkills(AgentReachDomain):
    pass


@pytest.mark.asyncio
async def test_reach_search_success():
    skills = MockSkills()
    with patch("skills.domains.agent_reach.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.search.return_value = {"ok": True, "text": "Results found", "items": [{"title": "Test"}]}
        mock_get_client.return_value = mock_client

        res = await skills._adapter_reach_search("github", "agent-reach", limit=5)
        assert res["ok"] is True
        assert res["text"] == "Results found"
        mock_client.search.assert_awaited_once_with(channel="github", query="agent-reach", limit=5, backend=None)


@pytest.mark.asyncio
async def test_reach_search_validation():
    skills = MockSkills()
    with pytest.raises(SkillError, match="Platform channel must be specified"):
        await skills._adapter_reach_search("", "query")

    with pytest.raises(SkillError, match="Search query must be specified"):
        await skills._adapter_reach_search("github", "   ")


@pytest.mark.asyncio
async def test_reach_read_success():
    skills = MockSkills()
    with patch("skills.domains.agent_reach.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.read.return_value = {"ok": True, "text": "Article content"}
        mock_get_client.return_value = mock_client

        res = await skills._adapter_reach_read("https://reddit.com/r/python")
        assert res["ok"] is True
        assert res["text"] == "Article content"
        mock_client.read.assert_awaited_once_with(url="https://reddit.com/r/python", backend=None)


@pytest.mark.asyncio
async def test_reach_read_validation():
    skills = MockSkills()
    with pytest.raises(SkillError, match="URL must be specified"):
        await skills._adapter_reach_read("")


@pytest.mark.asyncio
async def test_reach_transcript_success():
    skills = MockSkills()
    with patch("skills.domains.agent_reach.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.transcript.return_value = {"ok": True, "text": "Video transcript"}
        mock_get_client.return_value = mock_client

        res = await skills._adapter_reach_transcript("https://youtube.com/watch?v=123")
        assert res["ok"] is True
        assert res["text"] == "Video transcript"
        mock_client.transcript.assert_awaited_once_with(url="https://youtube.com/watch?v=123")


@pytest.mark.asyncio
async def test_reach_transcript_validation():
    skills = MockSkills()
    with pytest.raises(SkillError, match="URL must be specified"):
        await skills._adapter_reach_transcript("   ")


@pytest.mark.asyncio
async def test_reach_status_success():
    skills = MockSkills()
    with patch("skills.domains.agent_reach.get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.status.return_value = {"ok": True, "status": "ok", "channels": ["github", "youtube"]}
        mock_get_client.return_value = mock_client

        res = await skills._adapter_reach_status()
        assert res["ok"] is True
        assert res["status"] == "ok"
        assert "github" in res["channels"]
