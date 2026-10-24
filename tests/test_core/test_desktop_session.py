"""Desktop session environment recovery from runtime socket nodes."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import tempfile
import unittest

from core.desktop_session import recover_desktop_environment, wait_for_desktop_environment


class DesktopSessionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_socket(self, path: Path) -> socket.socket:
        path.parent.mkdir(parents=True, exist_ok=True)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path))
        self.addCleanup(listener.close)
        return listener

    def env(self, **values):
        return {"XDG_RUNTIME_DIR": str(self.runtime), **values}

    def test_recovers_unique_wayland_and_hyprland_sockets(self):
        self.make_socket(self.runtime / "wayland-1")
        self.make_socket(self.runtime / "hypr" / "instance-abc" / ".socket.sock")

        self.assertEqual(recover_desktop_environment(self.env()), {
            "WAYLAND_DISPLAY": "wayland-1",
            "HYPRLAND_INSTANCE_SIGNATURE": "instance-abc",
        })

    def test_preserves_explicit_values_and_only_recovers_missing_values(self):
        self.make_socket(self.runtime / "wayland-1")
        self.make_socket(self.runtime / "hypr" / "live-instance" / ".socket.sock")

        self.assertEqual(recover_desktop_environment(self.env(
            WAYLAND_DISPLAY="custom-wayland",
        )), {"HYPRLAND_INSTANCE_SIGNATURE": "live-instance"})
        self.assertEqual(recover_desktop_environment(self.env(
            WAYLAND_DISPLAY="", HYPRLAND_INSTANCE_SIGNATURE="custom-hypr",
        )), {})

    def test_ambiguity_leaves_the_variable_unset(self):
        self.make_socket(self.runtime / "wayland-1")
        self.make_socket(self.runtime / "wayland-2")
        self.make_socket(self.runtime / "hypr" / "instance-one" / ".socket.sock")
        self.make_socket(self.runtime / "hypr" / "instance-two" / ".socket.sock")

        self.assertEqual(recover_desktop_environment(self.env()), {})

    def test_ignores_non_socket_files_and_directories(self):
        (self.runtime / "wayland-1").write_text("not a socket")
        (self.runtime / "hypr" / "instance-dir" / ".socket.sock").parent.mkdir(parents=True)
        (self.runtime / "hypr" / "instance-dir" / ".socket.sock").touch()

        self.assertEqual(recover_desktop_environment(self.env()), {})

    def test_no_runtime_directory_means_no_inference(self):
        self.make_socket(self.runtime / "wayland-1")
        self.assertEqual(recover_desktop_environment({}), {})

    def test_wait_reports_missing_desktop_identifiers_at_timeout(self):
        recovered, missing = wait_for_desktop_environment(self.env(), timeout=0)
        self.assertEqual(recovered, {})
        self.assertEqual(missing, ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"))

    def test_wait_returns_immediately_when_desktop_is_ready(self):
        self.make_socket(self.runtime / "wayland-1")
        self.make_socket(self.runtime / "hypr" / "instance-abc" / ".socket.sock")
        recovered, missing = wait_for_desktop_environment(self.env(), timeout=1)
        self.assertEqual(recovered, {
            "WAYLAND_DISPLAY": "wayland-1",
            "HYPRLAND_INSTANCE_SIGNATURE": "instance-abc",
        })
        self.assertEqual(missing, ())


if __name__ == "__main__":
    unittest.main()
