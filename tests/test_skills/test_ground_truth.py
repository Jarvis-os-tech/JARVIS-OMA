"""Tests for ground-truth verification engine and integration with skills and TaskRunner."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from filesystem.task_runner import TaskRunner, TaskPlanError
from skills import ground_truth, system_control
from skills.skills import DesktopSkills


class GroundTruthUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_verify_file_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            
            # 1. Non-existent file
            res = await ground_truth.verify_file_state(str(file_path), timeout=0.1)
            self.assertFalse(res["verified"])
            self.assertIn("does not exist", res["reason"])

            # 2. Existing file with content
            file_path.write_text("Hello Ground Truth World", encoding="utf-8")
            res2 = await ground_truth.verify_file_state(str(file_path), min_bytes=5, timeout=0.2)
            self.assertTrue(res2["verified"])
            self.assertEqual(res2["details"]["size_bytes"], len("Hello Ground Truth World"))

            # 3. File size below min_bytes
            res3 = await ground_truth.verify_file_state(str(file_path), min_bytes=1000, timeout=0.1)
            self.assertFalse(res3["verified"])
            self.assertIn("less than expected", res3["reason"])

            # 4. Expected content snippet match
            res4 = await ground_truth.verify_file_state(str(file_path), expected_content="Ground Truth", timeout=0.2)
            self.assertTrue(res4["verified"])
            self.assertTrue(res4["details"]["content_matched"])

            # 5. Expected content snippet mismatch
            res5 = await ground_truth.verify_file_state(str(file_path), expected_content="Missing String", timeout=0.1)
            self.assertFalse(res5["verified"])
            self.assertIn("content snippet was not found", res5["reason"])

            # 6. Directory verification
            sub_dir = Path(tmpdir) / "sub"
            sub_dir.mkdir()
            res_dir = await ground_truth.verify_file_state(str(sub_dir), is_dir=True, timeout=0.2)
            self.assertTrue(res_dir["verified"])

    async def test_verify_process_state(self):
        # 1. Current running process PID
        res = await ground_truth.verify_process_state(os.getpid(), expected_running=True, timeout=0.2)
        self.assertTrue(res["verified"])
        self.assertTrue(res["details"]["running"])

        # 2. Definitely dead PID
        res2 = await ground_truth.verify_process_state(9999999, expected_running=True, timeout=0.1)
        self.assertFalse(res2["verified"])

        # 3. Process name check via mocked pgrep
        with patch("shutil.which", return_value="/usr/bin/pgrep"):
            with patch("skills.ground_truth._run_command", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = (0, "1234\n5678", "")
                res3 = await ground_truth.verify_process_state("python", expected_running=True, timeout=0.2)
                self.assertTrue(res3["verified"])
                self.assertIn(1234, res3["details"]["pids"])

    @patch("skills.system_control._query_open_windows")
    @patch("skills.system_control._query_active_window")
    @patch("shutil.which", return_value="/usr/bin/hyprctl")
    async def test_verify_window_state(self, mock_which, mock_active, mock_open):
        mock_open.return_value = [
            {"address": "0x1", "class": "antigravity", "title": "Antigravity Workspace"},
            {"address": "0x2", "class": "foot", "title": "terminal"},
        ]
        mock_active.return_value = {"address": "0x1", "class": "antigravity"}

        # 1. Window open and active
        res = await ground_truth.verify_window_state("antigravity", expected_active=True, expected_open=True, timeout=0.1)
        self.assertTrue(res["verified"])
        self.assertTrue(res["details"]["is_open"])
        self.assertTrue(res["details"]["is_active"])

        # 2. Window open but not active
        res2 = await ground_truth.verify_window_state("foot", expected_active=True, timeout=0.1)
        self.assertFalse(res2["verified"])
        self.assertTrue(res2["details"]["is_open"])
        self.assertFalse(res2["details"]["is_active"])

        # 3. Window not open
        res3 = await ground_truth.verify_window_state("nonexistent-app", expected_open=True, timeout=0.1)
        self.assertFalse(res3["verified"])
        self.assertFalse(res3["details"]["is_open"])

    @patch("shutil.which", return_value="/usr/bin/wl-paste")
    @patch("skills.ground_truth._run_command", new_callable=AsyncMock)
    async def test_verify_clipboard_state(self, mock_run, mock_which):
        mock_run.return_value = (0, "https://github.com/google/artemis.git", "")

        # 1. Matches snippet
        res = await ground_truth.verify_clipboard_state(expected_snippet="google/artemis", timeout=0.1)
        self.assertTrue(res["verified"])
        self.assertTrue(res["details"]["snippet_matched"])

        # 2. Mismatches snippet
        res2 = await ground_truth.verify_clipboard_state(expected_snippet="something-else", timeout=0.1)
        self.assertFalse(res2["verified"])
        self.assertIn("does not contain expected snippet", res2["reason"])

    async def test_universal_verify_ground_truth(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"verified content")
            f_path = f.name
        try:
            res = await ground_truth.verify_ground_truth("file", {"path": f_path, "min_bytes": 5})
            self.assertTrue(res["verified"])

            res_unknown = await ground_truth.verify_ground_truth("unknown_type", {})
            self.assertFalse(res_unknown["verified"])
            self.assertIn("unknown target_type", res_unknown["reason"])
        finally:
            if os.path.exists(f_path):
                os.unlink(f_path)


class DesktopSkillsGroundTruthIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.skills = DesktopSkills()

    def test_manifest_declares_verify_ground_truth(self):
        self.assertIn("verify_ground_truth", self.skills._skills)

    @patch("skills.ground_truth.verify_ground_truth", new_callable=AsyncMock)
    async def test_execute_verify_ground_truth(self, mock_verify):
        mock_verify.return_value = {"verified": True, "target_type": "file", "details": {}}
        res = await self.skills.execute("verify_ground_truth", {"target_type": "file", "criteria": {"path": "/tmp/test"}})
        self.assertTrue(res["verified"])
        mock_verify.assert_awaited_once_with("file", {"path": "/tmp/test"})

    @patch("skills.ground_truth.verify_clipboard_state", new_callable=AsyncMock)
    @patch("asyncio.create_subprocess_exec")
    async def test_write_clipboard_verifies_ground_truth(self, mock_exec, mock_verify_clip):
        proc_mock = AsyncMock()
        proc_mock.communicate = AsyncMock(return_value=(b"", b""))
        proc_mock.returncode = 0
        mock_exec.return_value = proc_mock
        mock_verify_clip.return_value = {"verified": True}

        res = await self.skills._adapter_write_clipboard("test clipboard data")
        self.assertEqual(res["status"], "written")
        self.assertTrue(res["ground_truth_verified"])
        mock_verify_clip.assert_awaited_once_with(expected_snippet="test clipboard data"[:50], timeout=1.0)


class TaskRunnerGroundTruthTests(unittest.IsolatedAsyncioTestCase):
    async def test_task_runner_ground_truth_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "output.txt"

            async def mock_execute(tool, args):
                target_file.write_text("Hello Step", encoding="utf-8")
                return {"status": "written"}

            runner = TaskRunner(mock_execute, lambda t, a: True)
            plan = json.dumps([{"tool": "write_file", "args": {"path": str(target_file)}}])
            res = runner.start("test task", plan)
            
            # Wait for completion
            for _ in range(20):
                await asyncio.sleep(0.05)
                status = runner.status(res["id"])
                if status["status"] in ("completed", "failed"):
                    break

            self.assertEqual(status["status"], "completed")
            self.assertEqual(status["completed_steps"], 1)

    async def test_task_runner_ground_truth_detects_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_file = Path(tmpdir) / "never_created.txt"

            async def mock_execute_lying(tool, args):
                # Returns success without actually writing the file to disk!
                return {"status": "written"}

            runner = TaskRunner(mock_execute_lying, lambda t, a: True)
            plan = json.dumps([{"tool": "write_file", "args": {"path": str(missing_file)}}])
            res = runner.start("lying task", plan)

            for _ in range(20):
                await asyncio.sleep(0.05)
                status = runner.status(res["id"])
                if status["status"] in ("completed", "failed"):
                    break

            self.assertEqual(status["status"], "failed")
            self.assertIn("Ground-truth verification failed", status["steps"][0]["error"])
