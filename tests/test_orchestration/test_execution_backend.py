import unittest

from orchestration.execution_backend import (
    ProcessExecutionBackend,
    TmuxExecutionBackend,
    available_backends,
)


class ExecutionBackendTests(unittest.TestCase):
    def test_capabilities_are_serializable_and_explicit(self):
        descriptor = TmuxExecutionBackend().describe()
        self.assertEqual(descriptor["name"], "tmux")
        self.assertTrue(descriptor["visible"])
        self.assertTrue(descriptor["supports_parallel"])
        self.assertTrue(descriptor["supports_steer"])

    def test_process_backend_is_always_available(self):
        self.assertEqual(available_backends(tmux=False), [ProcessExecutionBackend().describe()])

    def test_tmux_is_optional(self):
        names = [item["name"] for item in available_backends(tmux=True)]
        self.assertEqual(names, ["process", "tmux"])


if __name__ == "__main__":
    unittest.main()
