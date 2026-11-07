import pytest
from jarvis_control.package_manager import uninstall_package
from unittest.mock import patch, MagicMock

@patch("jarvis_control.package_manager.shutil.which")
@patch("jarvis_control.package_manager.subprocess.run")
def test_uninstall_pacman_success(mock_run, mock_which):
    # Setup
    mock_which.side_effect = lambda name: name == "pacman"
    mock_run.return_value = MagicMock(stdout="removed package")

    # Run
    result = uninstall_package("test-app")

    # Assert
    assert result == "removed package"
    mock_run.assert_called_with(["sudo", "pacman", "-Rns", "--noconfirm", "test-app"], capture_output=True, text=True, check=True)

@patch("jarvis_control.package_manager.shutil.which")
def test_uninstall_no_manager_found(mock_which):
    # Setup
    mock_which.return_value = None

    # Run
    result = uninstall_package("test-app")

    # Assert
    assert result == "ERROR: No supported package manager found."
