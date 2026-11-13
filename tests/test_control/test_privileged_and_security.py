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


# --- 5. Multi-Angle Hardening Tests ---

def test_normalize_package_name_and_prefix_family_blocking():
    from jarvis_control.security import normalize_package_name

    # Normalization tests
    assert normalize_package_name("extra/hyprland") == "hyprland"
    assert normalize_package_name("core/linux>=6.0") == "linux"
    assert normalize_package_name("community/vlc") == "vlc"

    # Family prefix protections
    family_protected = [
        "extra/hyprland",
        "hyprland-git",
        "pipewire-pulse",
        "pipewire-alsa",
        "wireplumber-git",
        "linux-zen",
        "linux-hardened",
        "systemd-libs",
        "systemd-sysvcompat",
        "sudo-git",
        "hyprland>=0.40.0",
        "pipewire-audio>=1.0",
    ]
    for pkg in family_protected:
        assert is_protected_package(pkg) is True, f"Expected {pkg} to be recognized as protected"
        with pytest.raises(ProtectedPackageError):
            check_package_removal(pkg)

    # Safe package variants should still be permitted
    safe_pkgs = ["vlc", "extra/vlc", "neovim-qt", "firefox-developer-edition"]
    for pkg in safe_pkgs:
        assert is_protected_package(pkg) is False, f"Expected {pkg} to be allowed"
        check_package_removal(pkg)


def test_flag_injection_rejection_in_package_removal():
    for flag in ("--nodeps", "-f", "-R", "--cascade"):
        with pytest.raises(ProtectedPackageError) as exc_info:
            check_package_removal([flag, "vlc"])
        assert "Invalid package name argument" in str(exc_info.value)

        err = validate_package_removal([flag, "htop"])
        assert err is not None
        assert "Invalid package name argument" in err


def test_critical_system_services_protection():
    # Blocking stop, disable, mask on critical infrastructure
    critical_cases = [
        ("dbus", "stop"),
        ("dbus.service", "disable"),
        ("pipewire", "stop"),
        ("pipewire.service", "mask"),
        ("wireplumber", "stop"),
        ("systemd-journald", "stop"),
        ("systemd-logind", "stop"),
        ("jarvis-voice", "stop"),
        ("hyprland", "stop"),
    ]
    for unit, action in critical_cases:
        res = execute_manage_system_service(unit, action, scope="system")
        assert res["ok"] is False
        assert "Refusing to" in res["output"]
        assert "protected core system service" in res["output"]

    # Allowed safe inspection or restart on services
    with patch("jarvis_control.privileged.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="active", stderr="")
        res_status = execute_manage_system_service("pipewire", "status", scope="user")
        assert res_status["ok"] is True


def test_execute_manage_packages_install_flag_filtering_and_yay_fallback():
    # Reject flag injection on install
    res_flags = execute_manage_packages("install", ["--nodeps", "-f"])
    assert res_flags["ok"] is False
    assert "No valid package names provided" in res_flags["output"]

    # When pacman fails with 'target not found', fallback to unprivileged yay with SUDO_ASKPASS
    with patch("jarvis_control.privileged.run_privileged_action") as mock_pacman, \
         patch("jarvis_control.privileged.subprocess.run") as mock_yay, \
         patch("jarvis_control.privileged.set_voice_listening_paused") as mock_pause:
        
        mock_pacman.return_value = {"ok": False, "output": "error: target not found: custom-aur-pkg", "code": 1}
        mock_yay.return_value = MagicMock(returncode=0, stdout="Installed from AUR", stderr="")

        res = execute_manage_packages("install", ["custom-aur-pkg"])
        assert res["ok"] is True
        assert "Installed from AUR" in res["output"]

        # Confirm yay was called unprivileged directly without sudo
        yay_cmd = mock_yay.call_args[0][0]
        assert yay_cmd[0] == "yay"
        assert yay_cmd[1] == "-S"
        assert "custom-aur-pkg" in yay_cmd


def test_execute_modify_system_config_batches_privileged_commands():
    with patch("jarvis_control.privileged.run_privileged_action") as mock_priv:
        mock_priv.return_value = {"ok": True, "output": "Updated", "code": 0}
        
        res = execute_modify_system_config(
            path="/etc/sysctl.d/99-jarvis-test.conf",
            patch_or_content="vm.swappiness=20\n",
            reason="Tuning swappiness"
        )
        assert res["ok"] is True
        mock_priv.assert_called_once()
        call_cmd = mock_priv.call_args[0][0]
        # Verify single batched bash -c command with backup, cp, and chmod
        assert call_cmd[0] == "bash"
        assert call_cmd[1] == "-c"
        assert ".jarvis.bak" in call_cmd[2]
        assert "chmod 644" in call_cmd[2]


def test_jarvis_askpass_graceful_exit_without_display():
    import subprocess
    import sys
    from pathlib import Path

    askpass_path = Path(__file__).parent.parent.parent / "bin" / "jarvis-askpass"
    # Execute with stripped DISPLAY and WAYLAND_DISPLAY
    env = {"PATH": "/usr/bin:/bin"}
    proc = subprocess.run([sys.executable, str(askpass_path)], env=env, capture_output=True, text=True)
    assert proc.returncode == 1
    assert "failed initializing display dialog" in proc.stderr
