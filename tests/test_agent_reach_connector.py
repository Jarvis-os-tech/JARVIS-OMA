"""Tests for JARVIS OS Agent Reach Connector."""
import pytest
from unittest.mock import patch, MagicMock
from connectors.agent_reach import AgentReachClient, AgentReachError

@pytest.fixture
def client():
    return AgentReachClient(base_url="http://127.0.0.1:8765")

@pytest.mark.asyncio
async def test_client_is_available(client):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_resp
        
        available = await client.is_available()
        assert available is True

@pytest.mark.asyncio
async def test_client_read_success(client):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": True,
            "items": [
                {
                    "title": "Example Post",
                    "url": "https://reddit.com/r/python/123",
                    "author": "dev",
                    "text": "Detailed content here"
                }
            ]
        }
        mock_post.return_value = mock_resp

        result = await client.read("https://reddit.com/r/python/123")
        assert result["ok"] is True
        assert "Detailed content here" in result["text"]

@pytest.mark.asyncio
async def test_client_read_error(client):
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": False,
            "error": {"code": "NEED_LOGIN", "message": "Login required"}
        }
        mock_post.return_value = mock_resp

        result = await client.read("https://reddit.com/r/python/123")
        assert result["ok"] is False
        assert result["error_code"] == "NEED_LOGIN"
