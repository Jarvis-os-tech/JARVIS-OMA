"""Tests for jarvis-memory CLI wrapper and subcommands."""
import json
import tempfile
import unittest
from pathlib import Path

from jarvis_memory.__main__ import main


class MemoryCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config_path = Path(self.directory.name) / "config.json"
        self.config_path.write_text(
            json.dumps({"memory": {"path": str(Path(self.directory.name) / "state")}}),
            encoding="utf-8",
        )

    def test_cli_help(self):
        # Without args prints help and returns 0
        self.assertEqual(main([]), 0)
        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_cli_stats(self):
        self.assertEqual(main(["--config", str(self.config_path), "stats"]), 0)
        self.assertEqual(main(["--config", str(self.config_path), "--json", "stats"]), 0)

    def test_cli_store_and_search(self):
        ret = main(["--config", str(self.config_path), "store", "Prefers", "concise", "replies."])
        self.assertEqual(ret, 0)
        ret_search = main(["--config", str(self.config_path), "search", "replies"])
        self.assertEqual(ret_search, 0)

    def test_cli_clear(self):
        main(["--config", str(self.config_path), "store", "Temporary fact"])
        ret = main(["--config", str(self.config_path), "clear"])
        self.assertEqual(ret, 0)
        ret_json = main(["--config", str(self.config_path), "--json", "clear"])
        self.assertEqual(ret_json, 0)


if __name__ == "__main__":
    unittest.main()
