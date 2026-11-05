"""Tests for Agent-Reach Daemon REST Service."""
import pytest
pytest.importorskip('fastapi', reason='Agent-Reach service tests use its separate FastAPI environment')
from fastapi.testclient import TestClient
import sys
import importlib.util
from pathlib import Path

# Add the agent-reach source path
agent_reach_src = Path.home() / ".local/share/agent-reach/src"
if str(agent_reach_src) not in sys.path:
    sys.path.insert(0, str(agent_reach_src))

daemon_path = agent_reach_src.parent / 'service' / 'daemon.py'
if not daemon_path.is_file():
    pytest.skip('Agent-Reach daemon is not installed on this machine', allow_module_level=True)
spec = importlib.util.spec_from_file_location('agent_reach_daemon_under_test', daemon_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = module.app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "agent-reach"
    assert "pid" in data

def test_channels_endpoint(client):
    response = client.get("/channels")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "channels" in data
    channel_names = [c["name"] for c in data["channels"]]
    assert "github" in channel_names
    assert "youtube" in channel_names
    assert "reddit" in channel_names

def test_search_validation(client):
    # Non-existent channel returns 404
    response = client.post("/search", json={"channel": "non_existent_platform", "query": "test"})
    assert response.status_code == 404
