"""Unit tests for privileged execution, core OS package denylist protection,
and full-range system tools.
"""
import pytest
from unittest.mock import patch, MagicMock
from jarvis_control.security import (
    is_protected_package,
    check_package_removal,
    validate_package_removal,
    ProtectedPackageError,
    CORE_PROTECTED_PACKAGES
)
from jarvis_control.package_manager import uninstall_package
from jarvis_control.privileged import (
    build_btrfs_snapshot_command,
    run_privileged_action,
    execute_manage_packages,
    execute_manage_system_service,
    execute_modify_system_config,
    execute_general_command
)
from jarvis_control.skills import ControlSkills, UnifiedSkills
from jarvis_control.config import Config


# --- 1. Denylist Protection Tests ---

def test_core_protected_packages_contains_required_components():
    required = {
        'base', 'linux', 'linux-cachyos', 'linux-omarchy', 'systemd',
        'hyprland', 'pipewire', 'wireplumber', 'btrfs-progs', 'cryptsetup', 'sudo'
    }
    for pkg in required:
        assert pkg in CORE_PROTECTED_PACKAGES
        assert is_protected_package(pkg) is True


def test_denylist_blocks_critical_packages():
    # Specific verification targets
    for pkg in ('linux-cachyos', 'hyprland', 'pipewire', 'systemd', 'sudo'):
        with pytest.raises(ProtectedPackageError) as exc_info:
            check_package_removal(pkg)
        assert pkg in str(exc_info.value)
        assert validate_package_removal(pkg) is not None


def test_denylist_allows_safe_packages():
    for pkg in ('vlc', 'neovim', 'htop', 'firefox', 'ripgrep'):
        assert is_protected_package(pkg) is False
        assert validate_package_removal(pkg) is None
        # Does not raise
        check_package_removal(pkg)


def test_package_manager_blocks_protected_packages():
    for pkg in ('linux-cachyos', 'hyprland', 'pipewire'):
        result = uninstall_package(pkg)
        assert result.startswith("ERROR:")
        assert "critical OS package" in result or "protected" in result


# --- 2. Privileged Execution Engine Tests ---

def test_build_btrfs_snapshot_command():
    cmd = ["pacman", "-Rns", "--noconfirm", "vlc"]
    wrapped = build_btrfs_snapshot_command(cmd)
    assert wrapped[0] == "bash"
    assert wrapped[1] == "-c"
    assert "snapper" in wrapped[2]
    assert "btrfs subvolume snapshot" in wrapped[2]
    assert "pacman -Rns --noconfirm vlc" in wrapped[2]


@patch("jarvis_control.privileged.subprocess.run")
@patch("jarvis_control.privileged.set_voice_listening_paused")
@patch("jarvis_control.privileged.speak_explanation")
def test_run_privileged_action_normal(mock_speak, mock_pause, mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Success output", stderr="")
    
    res = run_privileged_action(
        command=["systemctl", "restart", "bluetooth"],
        reason="Restarting bluetooth service",
        destructive=False
    )

    assert res["ok"] is True
    assert res["output"] == "Success output"
    mock_speak.assert_called_once_with("Restarting bluetooth service")
    # Verify microphone paused and unpaused
    assert mock_pause.call_count == 2
    mock_pause.assert_any_call(True)
    mock_pause.assert_any_call(False)


@patch("jarvis_control.privileged.subprocess.run")
@patch("jarvis_control.privileged.set_voice_listening_paused")
@patch("jarvis_control.privileged.speak_explanation")
def test_run_privileged_action_destructive_triggers_snapshot(mock_speak, mock_pause, mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Uninstalled", stderr="")
    
    res = run_privileged_action(
        command=["pacman", "-Rns", "--noconfirm", "vlc"],
        reason="Uninstalling VLC",
        destructive=True
    )

    assert res["ok"] is True
    assert res["destructive"] is True
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "sudo"
    assert call_args[1] == "-A"
    assert "snapper" in call_args[4]  # Inside the batch script


# --- 3. Full-Range Tool Handlers Tests ---

def test_execute_manage_packages_blocks_denylist():
    res = execute_manage_packages("remove", ["linux-cachyos"])
    assert res["ok"] is False
    assert "critical OS package" in res["output"]


@patch("jarvis_control.privileged.run_privileged_action")
def test_execute_manage_packages_install(mock_priv):
    mock_priv.return_value = {"ok": True, "output": "installed", "code": 0}
    res = execute_manage_packages("install", ["vlc"])
    assert res["ok"] is True
    mock_priv.assert_called_once()
    assert mock_priv.call_args[1]["destructive"] is False


@patch("jarvis_control.privileged.subprocess.run")
def test_execute_manage_system_service_user_scope(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="active", stderr="")
    res = execute_manage_system_service("jarvis-voice", "status", scope="user")
    assert res["ok"] is True
    mock_run.assert_called_with(["systemctl", "--user", "status", "jarvis-voice.service"], capture_output=True, text=True, timeout=30)


@patch("jarvis_control.privileged.run_privileged_action")
def test_execute_manage_system_service_system_scope_restart(mock_priv):
    mock_priv.return_value = {"ok": True, "output": "restarted", "code": 0}
    res = execute_manage_system_service("docker", "restart", scope="system")
    assert res["ok"] is True
    mock_priv.assert_called_once()


# --- 4. UnifiedSkills Declarations and Execution Tests ---

@pytest.mark.asyncio
async def test_unified_skills_has_system_tools():
    ctrl = ControlSkills(Config())
    unified = UnifiedSkills(control_skills=ctrl)
    
    names = {t["name"] for t in unified.declarations}
    for expected in ("manage_packages", "manage_system_service", "modify_system_config", "execute_system_command"):
        assert expected in names, f"{expected} missing from UnifiedSkills declarations"


@pytest.mark.asyncio
async def test_unified_skills_package_denylist_execution():
    ctrl = ControlSkills(Config())
    unified = UnifiedSkills(control_skills=ctrl)
    
    result = await unified.execute("manage_packages", {"action": "remove", "packages": ["hyprland"]})
    assert "critical OS package" in result
