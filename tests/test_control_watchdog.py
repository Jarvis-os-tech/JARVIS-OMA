import asyncio
import unittest
from unittest.mock import MagicMock
from jarvis_control.skills import ControlSkills
from jarvis_control.config import Config

class TestControlWatchdog(unittest.IsolatedAsyncioTestCase):
    async def test_tool_exception_returns_error_string(self):
        config = Config()
        skills = ControlSkills(config)
        skills._tool_names = {"failing_tool"}

        def raise_func(*args, **kwargs):
            raise ValueError("Something went terribly wrong")

        skills.executor.call = raise_func

        res = await skills.execute("failing_tool", {})
        self.assertTrue(res.startswith("ERROR:"), f"Expected error string, got {res}")

        skills.executor.call = lambda *args, **kwargs: MagicMock(as_tool_result=lambda: "success")
        res2 = await skills.execute("failing_tool", {})
        self.assertEqual(res2, "success")

    async def test_shutdown_worker_rebuilds_and_retries(self):
        config = Config()
        skills = ControlSkills(config)
        skills._tool_names = {"any_tool"}

        skills._worker.shutdown(wait=True)
        skills._closed = False

        skills.executor.call = lambda *args, **kwargs: MagicMock(as_tool_result=lambda: "recovered")

        res = await skills.execute("any_tool", {})
        self.assertEqual(res, "recovered")

    async def test_close_idempotent(self):
        config = Config()
        skills = ControlSkills(config)

        await skills.close()
        await skills.close()
        self.assertTrue(skills._closed)

if __name__ == '__main__':
    unittest.main()
