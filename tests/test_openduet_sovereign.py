"""Tests for OpenDuet Sovereign De-Copilotized Stack in JARVIS OS."""

import json
import urllib.request
import pytest


@pytest.mark.asyncio
async def test_sovereign_intelligence_mock_health():
    """Verify the sovereign intelligence mock on port 3009 answers as valid."""
    req = urllib.request.Request("http://localhost:3009/health")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("status") == "ok"
        assert data.get("mode") == "sovereign"


@pytest.mark.asyncio
async def test_sovereign_intelligence_entitlements():
    """Verify runtime entitlements are mocked as enterprise active."""
    req = urllib.request.Request("http://localhost:3009/v1/entitlements")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("status") == "ready"
        assert data.get("entitlement", {}).get("active") is True


@pytest.mark.asyncio
async def test_openduet_core_server_license():
    """Verify OpenDuet core server returns valid license without cloud auth."""
    req = urllib.request.Request("http://localhost:3001/api/copilotkit/info")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("licenseStatus") == "valid"
        assert data.get("mode") == "sovereign"
        assert "agent-bot" in data.get("agents", {})


@pytest.mark.asyncio
async def test_openduet_single_user_capabilities():
    """Verify single-user mode is enabled and requires zero OAuth providers."""
    req = urllib.request.Request("http://localhost:3001/api/capabilities")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("localEvaluation") is True
        assert len(data.get("authProviders", [])) == 0


@pytest.mark.asyncio
async def test_openduet_web_app_responsive():
    """Verify OpenDuet Web UI answers on port 3010."""
    req = urllib.request.Request("http://localhost:3010/")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        assert resp.status == 200
        html = resp.read().decode()
        assert "OpenDuet" in html
