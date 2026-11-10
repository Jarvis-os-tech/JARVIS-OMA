import asyncio
import unittest
from unittest.mock import MagicMock
from jarvis_control.skills import ControlSkills
from jarvis_control.config import Config
import time

class TestControlConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_independent_calls_overlap(self):
        # Setup
        config = Config()
        skills = ControlSkills(config)
        skills._tool_names = {"any_tool"}

        # Mock executor.call to include a sleep
        def slow_func(*args, **kwargs):
            time.sleep(0.5)
            return MagicMock(as_tool_result=lambda: "result")

        skills.executor.call = slow_func

        # Run two calls concurrently
        start = time.perf_counter()
        t1 = asyncio.create_task(skills.execute("any_tool", {}))
        t2 = asyncio.create_task(skills.execute("any_tool", {}))

        results = await asyncio.gather(t1, t2)
        elapsed = time.perf_counter() - start

        # If serialized (max_workers=1), it would take 1.0s.
        # With concurrency (max_workers > 1), it should be < 1.0s.
        self.assertLess(elapsed, 0.9, f"Calls should be concurrent, but took {elapsed:.2f}s")
        self.assertEqual(results, ["result", "result"])

    async def test_timeout_returns_error(self):
        config = Config()
        skills = ControlSkills(config)
        skills._tool_names = {"any_tool"}

        def blocking_func(*args, **kwargs):
            time.sleep(1.0)
            return MagicMock(as_tool_result=lambda: "finished")

        skills.executor.call = blocking_func

        # Start call that should timeout
        t1 = asyncio.create_task(skills.execute("any_tool", {}, call_timeout=0.2))

        result = await t1
        self.assertIn("ERROR: timed out", result)

        # Check that a subsequent call still works
        skills.executor.call = lambda *args, **kwargs: MagicMock(as_tool_result=lambda: "second_call")
        t2 = asyncio.create_task(skills.execute("any_tool", {}))
        result2 = await t2
        self.assertEqual(result2, "second_call")

if __name__ == '__main__':
    unittest.main()
