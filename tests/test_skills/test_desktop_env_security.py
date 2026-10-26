"""Desktop child processes keep GUI state while dropping inherited credentials."""
import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

from core.secret_env import sanitized_subprocess_env
from skills import skills as skills_module
from skills import system_control


class DesktopEnvironmentSecurityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.parent_env = {
            "OPENAI_KEY": "synthetic-openai",
            "PRIVATE_KEY": "synthetic-private",
            "AUTH_BEARER": "synthetic-bearer",
            "GEMINI_API_KEY": "synthetic-gemini",
            "PATH": os.environ.get("PATH", ""),
            "WAYLAND_DISPLAY": "wayland-test",
            "XDG_RUNTIME_DIR": "/run/user/test",
        }

    async def test_skills_run_passes_sanitized_desktop_environment_to_real_child(self):
        skill = object.__new__(skills_module.DesktopSkills)
        skill._command_timeout = 5
        code = (
            "import os; print('|'.join(k for k in "
            "('OPENAI_KEY','PRIVATE_KEY','AUTH_BEARER','GEMINI_API_KEY',"
            "'WAYLAND_DISPLAY','XDG_RUNTIME_DIR') if os.getenv(k)))"
        )
        with patch.dict(os.environ, self.parent_env, clear=True):
            output = await skill._run(sys.executable, "-c", code)
        self.assertEqual(output, "WAYLAND_DISPLAY|XDG_RUNTIME_DIR")

    async def test_desktop_default_is_sanitized_and_keeps_runtime_environment(self):
        with patch.dict(os.environ, self.parent_env, clear=True):
            env = system_control._desktop_env()
            code, output, _ = await system_control._run_command(
                sys.executable,
                "-c",
                "import os; print('|'.join(k for k in "
                "('OPENAI_KEY','PRIVATE_KEY','AUTH_BEARER','GEMINI_API_KEY',"
                "'WAYLAND_DISPLAY','XDG_RUNTIME_DIR','OMARCHY_PATH') if os.getenv(k)))",
            )
        self.assertEqual(output, "WAYLAND_DISPLAY|XDG_RUNTIME_DIR|OMARCHY_PATH")
        self.assertEqual(code, 0)
        self.assertEqual(env["WAYLAND_DISPLAY"], "wayland-test")
        self.assertEqual(env["XDG_RUNTIME_DIR"], "/run/user/test")
        self.assertEqual(env["OMARCHY_PATH"], "/usr/share/omarchy")
        self.assertNotIn("OPENAI_KEY", env)
        self.assertNotIn("PRIVATE_KEY", env)
        self.assertNotIn("AUTH_BEARER", env)
        self.assertNotIn("GEMINI_API_KEY", env)

    async def test_launch_passes_sanitized_environment(self):
        skill = object.__new__(skills_module.DesktopSkills)
        process = type("Process", (), {"wait": AsyncMock(return_value=0)})()
        with (
            patch.dict(os.environ, self.parent_env, clear=True),
            patch("skills.skills.shutil.which", return_value=sys.executable),
            patch.object(asyncio, "create_subprocess_exec", new=AsyncMock(return_value=process)) as spawn,
        ):
            await skill._launch(sys.executable, "-c", "pass")
        self.assertEqual(spawn.await_args.kwargs["env"], sanitized_subprocess_env(self.parent_env))
        self.assertEqual(spawn.await_args.kwargs["start_new_session"], True)

    async def test_system_control_preserves_explicit_empty_environment(self):
        with patch.dict(os.environ, self.parent_env, clear=True):
            code, output, _ = await system_control._run_command(
                sys.executable,
                "-c",
                "import os; print(os.getenv('WAYLAND_DISPLAY', 'absent'))",
                env={},
            )
        self.assertEqual((code, output), (0, "absent"))

    async def test_inline_clipboard_child_gets_sanitized_environment(self):
        skill = object.__new__(skills_module.DesktopSkills)
        skill._command = lambda _: "wl-copy"
        process = type(
            "Process",
            (),
            {
                "returncode": 0,
                "communicate": AsyncMock(return_value=(b"", b"")),
            },
        )()
        with (
            patch.dict(os.environ, self.parent_env, clear=True),
            patch.object(asyncio, "create_subprocess_exec", new=AsyncMock(return_value=process)) as spawn,
            patch("skills.ground_truth.verify_clipboard_state", new=AsyncMock(return_value={"verified": True})),
        ):
            result = await skill._adapter_write_clipboard("hello")
        self.assertEqual(result["status"], "written")
        passed_env = spawn.await_args.kwargs["env"]
        self.assertEqual(passed_env, sanitized_subprocess_env(self.parent_env))
        self.assertNotIn("GEMINI_API_KEY", passed_env)
        self.assertEqual(passed_env["WAYLAND_DISPLAY"], "wayland-test")

    async def test_inline_overlay_probe_gets_sanitized_environment(self):
        skill = object.__new__(skills_module.DesktopSkills)
        skill.test_bar = type("TestBar", (), {"start": lambda self: "http://localhost/test"})()
        launched = AsyncMock()
        skill._launch = launched
        process = type("Process", (), {"wait": AsyncMock(return_value=0)})()
        with (
            patch.dict(os.environ, self.parent_env, clear=True),
            patch("os.path.isfile", return_value=True),
            patch.object(asyncio, "create_subprocess_exec", new=AsyncMock(return_value=process)) as spawn,
        ):
            result = await skill._adapter_open_input_bar()
        self.assertEqual(result["status"], "opened")
        self.assertEqual(spawn.await_args.kwargs["env"], sanitized_subprocess_env(self.parent_env))
        launched.assert_awaited_once()

