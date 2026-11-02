"""Tests for ControlSkills and UnifiedSkills integration."""
import pytest
from jarvis_control.skills import ControlSkills, UnifiedSkills
from jarvis_control.config import Config


@pytest.mark.asyncio
async def test_control_skills_system_query():
    skills = ControlSkills(Config())
    result = await skills.execute("system_query", {"topic": "os"})
    assert "Linux" in result or "Omarchy" in result


@pytest.mark.asyncio
async def test_control_skills_confirmation_flow():
    skills = ControlSkills(Config())
    # Action requiring confirmation
    res = await skills.execute("omarchy_cli", {"command": "reboot"})
    assert "needs spoken confirmation" in res

    # Rejection of invalid confirmation word
    reject_res = await skills.execute("confirm_last", {"heard_phrase": "banana"})
    assert "ERROR:" in reject_res
    assert "banana" in reject_res

    # Cancellation
    cancel_res = await skills.execute("cancel_last", {})
    assert "Cancelled:" in cancel_res


@pytest.mark.asyncio
async def test_unified_skills_delegation():
    class FakeMemory:
        def __init__(self):
            self.declarations = [{"name": "fake_recall", "description": "recall memory"}]
            self._closed = False

        async def execute(self, name, args):
            return f"memory_result_{name}"

        async def close_agent_jobs(self):
            self._closed = True

    fake_mem = FakeMemory()
    ctrl = ControlSkills(Config())
    unified = UnifiedSkills(memory_skills=fake_mem, control_skills=ctrl)

    # Declarations combine
    tool_names = {t["name"] for t in unified.declarations}
    assert "fake_recall" in tool_names
    assert "system_query" in tool_names
    assert "hypr_query" in tool_names

    # Memory dispatch
    mem_out = await unified.execute("fake_recall", {"q": "test"})
    assert mem_out == "memory_result_fake_recall"

    # Control dispatch
    ctrl_out = await unified.execute("system_query", {"topic": "os"})
    assert "Linux" in ctrl_out or "Omarchy" in ctrl_out

    # Close agent jobs
    await unified.close_agent_jobs()
    assert unified._closed is True


@pytest.mark.asyncio
async def test_control_adapter_accepts_voice_config_with_policy_defaults():
    from jarvis_voice.config import Config as VoiceConfig
    voice_config = VoiceConfig(allow_shell=False, dry_run=False, tasks_enabled=False, vision_enabled=False)
    skills = ControlSkills(voice_config)
    assert skills.config.deny_patterns
    assert skills.config.confirm_patterns
    assert not skills.config.tasks_enabled
    result = await skills.execute('system_query', {'topic': 'time'})
    assert not result.startswith('ERROR:')
    held = await skills.execute('omarchy_cli', {'command': 'reboot'})
    assert 'needs spoken confirmation' in held
    assert 'Cancelled:' in skills.cancel()


@pytest.mark.asyncio
async def test_disabled_tools_cannot_be_called_and_camera_is_cleaned_up(monkeypatch):
    from unittest.mock import Mock
    skills = ControlSkills(Config(tasks_enabled=False, vision_enabled=False, allow_shell=False))
    camera_stop = Mock()
    monkeypatch.setattr(skills.executor.vision, 'stop_owned', camera_stop)
    for name in ('task_submit', 'camera_view', 'shell'):
        assert 'not enabled' in await skills.execute(name, {})
    await skills.close()
    await skills.close()
    camera_stop.assert_called_once()


@pytest.mark.asyncio
async def test_unified_skills_with_desktop_skills():
    from skills.skills import DesktopSkills
    import json

    ctrl = ControlSkills(Config())
    desktop = DesktopSkills()
    unified = UnifiedSkills(control_skills=ctrl, desktop_skills=desktop)

    # Declarations combine across control and desktop
    tool_names = {t["name"] for t in unified.declarations}
    assert "system_query" in tool_names
    assert "hypr_query" in tool_names
    assert "github_connection_status" in tool_names
    assert "google_connection_status" in tool_names
    assert "phone_status" in tool_names
    assert len(unified.declarations) > 200

    # Dispatch to control tool
    ctrl_out = await unified.execute("system_query", {"topic": "os"})
    assert "Linux" in ctrl_out or "Omarchy" in ctrl_out

    # Dispatch to desktop tool (GitHub status)
    gh_out = await unified.execute("github_connection_status", {})
    gh_data = json.loads(gh_out)
    assert gh_data.get("success") is True or "setup_required" in gh_data

    # Dispatch to desktop tool (Google status)
    google_out = await unified.execute("google_connection_status", {})
    google_data = json.loads(google_out)
    assert google_data.get("success") is True or "setup_required" in google_data

    # Dispatch to phone status (gracefully handle headless test environments lacking D-Bus telephony)
    try:
        phone_out = await unified.execute("phone_status", {})
        phone_data = json.loads(phone_out)
        assert "connected" in phone_data
    except Exception as err:
        assert "Phone" in str(err) or "Telephony" in str(err)

    # Close agent jobs
    await unified.close_agent_jobs()
    assert unified._closed is True


@pytest.mark.asyncio
async def test_unified_skills_enter_standby():
    import json
    from skills.skills import DesktopSkills
    ctrl = ControlSkills(Config())
    desktop = DesktopSkills()
    unified = UnifiedSkills(control_skills=ctrl, desktop_skills=desktop)

    # Standby declaration is registered
    tool_names = {t["name"] for t in unified.declarations}
    assert "enter_standby" in tool_names

    # Calling without standby callback
    res = await unified.execute("enter_standby", {})
    data = json.loads(res)
    assert "error" in data or data.get("status") == "error"

    # Wire callback
    called = []
    def _cb():
        called.append(True)
    unified.on_standby_request = _cb
    desktop.on_standby_request = _cb

    # Calling on unified triggers callback
    res2 = await unified.execute("enter_standby", {})
    data2 = json.loads(res2)
    assert data2.get("status") == "standby_requested"
    assert data2.get("wake_phrase") == "Hey Jarvis"
    assert len(called) == 1

    # Calling desktop skill directly also triggers callback
    desktop_res = await desktop.execute("enter_standby", {})
    assert desktop_res.get("status") == "standby_requested"
    assert len(called) == 2


def test_direct_task_worker_imports_without_compatibility_shim(tmp_path):
    import os
    from pathlib import Path
    import shutil
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / 'jarvis_control', tmp_path / 'jarvis_control',
                    ignore=shutil.ignore_patterns('__pycache__'))
    # Match systemd's direct-file launch; run_name avoids starting a real task.
    code = "import runpy; runpy.run_path('jarvis_control/task_worker.py', run_name='worker_import_check')"
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env,
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_control_skills_read_url(monkeypatch):
    skills = ControlSkills(Config())
    tool_names = {t["name"] for t in skills.declarations}
    assert "read_url" in tool_names

    monkeypatch.setattr(
        'jarvis_control.web_text.bounded_page_text',
        lambda url, timeout=12: "Extracted article text for testing",
    )

    result = await skills.execute("read_url", {"url": "https://example.com/test"})
    assert "Extracted article text for testing" in result

    # Invalid URL scheme rejected safely
    invalid_result = await skills.execute("read_url", {"url": "ftp://example.com"})
    assert "http or https address" in invalid_result

