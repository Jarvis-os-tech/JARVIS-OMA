"""Automated verification suite for Voice Core Immutability Lock and Extension Architecture."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock

from orchestration.evolution import EvolutionError, EvolutionManager, LOCKED_VOICE_PATHS
from scripts.verify_voice_lock import load_manifest, verify_file_hashes, verify_git_diff
from audio.extension import (
    AudioExtensionRegistry,
    AudioFrameProcessor,
    AudioHook,
    ExtendedAudioEngine,
)


class VoiceLockManifestTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent.parent
        self.manifest_path = self.repo_root / "audio/.voice_lock.json"

    def test_manifest_exists_and_contains_core_files(self):
        self.assertTrue(self.manifest_path.is_file(), "Manifest file must exist")
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        locked_files = manifest.get("locked_files", {})
        expected_keys = {
            "audio/engine.py",
            "audio/downstream.py",
            "audio/echo_cancel.py",
            "audio/__init__.py",
            "echo_cancel.py",
            "tests/test_audio/test_engine.py",
            "tests/test_audio/test_echo_cancel.py",
        }
        self.assertEqual(set(locked_files.keys()), expected_keys)

    def test_sha256_hashes_match_disk(self):
        manifest = load_manifest(self.repo_root)
        violations = verify_file_hashes(self.repo_root, manifest)
        self.assertEqual(violations, [], f"Voice core files modified: {violations}")

    def test_tamper_detection(self):
        manifest = {
            "locked_files": {
                "audio/engine.py": {"sha256": "invalid_hash_00000000000000000000000000000000"}
            }
        }
        violations = verify_file_hashes(self.repo_root, manifest)
        self.assertEqual(len(violations), 1)
        self.assertIn("checksum mismatch", violations[0])

    def test_verify_script_exit_code_zero(self):
        script = self.repo_root / "scripts/verify_voice_lock.py"
        res = subprocess.run([sys.executable, str(script)], cwd=self.repo_root, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Script failed: {res.stderr}")
        self.assertIn("Voice core lock verified", res.stdout)


class EvolutionVoiceGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_evolution_rejects_mutation_to_locked_voice_file(self):
        mock_job = {
            "checkout": "/tmp/fake_checkout",
            "source_head": "HEAD~1",
        }
        manager = EvolutionManager(orchestrator=MagicMock(), read_only=True)

        async def fake_git(job, cwd, *args, **kwargs):
            return {
                "exit_code": 0,
                "output": "audio/engine.py\nother_module.py\n",
                "output_truncated": False,
            }

        manager._git = fake_git
        with self.assertRaises(EvolutionError) as ctx:
            await manager._check_voice_lock(mock_job)
        self.assertIn("Mutation of locked voice core file rejected", str(ctx.exception))
        self.assertIn("audio/engine.py", str(ctx.exception))

    async def test_evolution_permits_unlocked_files(self):
        mock_job = {
            "checkout": "/tmp/fake_checkout",
            "source_head": "HEAD~1",
        }
        manager = EvolutionManager(orchestrator=MagicMock(), read_only=True)

        async def fake_git(job, cwd, *args, **kwargs):
            return {
                "exit_code": 0,
                "output": "new_feature.py\naudio/extension.py\n",
                "output_truncated": False,
            }

        manager._git = fake_git
        # Should not raise any error
        await manager._check_voice_lock(mock_job)


class AudioExtensionArchitectureTests(unittest.IsolatedAsyncioTestCase):
    def test_registry_registration_and_priority(self):
        registry = AudioExtensionRegistry()

        class LowPriorityProcessor:
            def process_input_frame(self, frame: bytes) -> bytes | None:
                return frame + b"_low"
            def process_output_frame(self, frame: bytes) -> bytes | None:
                return frame + b"_low"

        class HighPriorityProcessor:
            def process_input_frame(self, frame: bytes) -> bytes | None:
                return frame + b"_high"
            def process_output_frame(self, frame: bytes) -> bytes | None:
                return frame + b"_high"

        low = LowPriorityProcessor()
        high = HighPriorityProcessor()
        registry.register_processor(low, priority=200)
        registry.register_processor(high, priority=10)

        out_input = registry.apply_input_frame(b"pcm")
        self.assertEqual(out_input, b"pcm_high_low")

        out_output = registry.apply_output_frame(b"pcm")
        self.assertEqual(out_output, b"pcm_high_low")

        self.assertTrue(registry.unregister_processor(high))
        self.assertEqual(registry.apply_input_frame(b"pcm"), b"pcm_low")

    def test_hook_event_dispatch(self):
        registry = AudioExtensionRegistry()
        events = []

        class TestHook:
            def on_state_change(self, state: str) -> None:
                events.append(f"state:{state}")
            def on_barge_in(self) -> None:
                events.append("barge_in")
            def on_turn_started(self) -> None:
                events.append("turn_started")
            def on_turn_completed(self) -> None:
                events.append("turn_completed")

        hook = TestHook()
        registry.register_hook(hook)

        registry.dispatch_state_change("speaking")
        registry.dispatch_barge_in()
        registry.dispatch_turn_started()
        registry.dispatch_turn_completed()

        self.assertEqual(events, ["state:speaking", "barge_in", "turn_started", "turn_completed"])

    async def test_extended_audio_engine_composition(self):
        fake_base = MagicMock()
        fake_base.async_input_queue = asyncio.Queue()
        fake_base.c_output_queue = MagicMock()
        fake_base.active_generation = 7

        extended = ExtendedAudioEngine(base_engine=fake_base)

        # Register a processor that adds header bytes
        class HeaderProcessor:
            def process_input_frame(self, frame: bytes) -> bytes | None:
                return b"EXT_" + frame
            def process_output_frame(self, frame: bytes) -> bytes | None:
                return b"OUT_" + frame

        extended.register_processor(HeaderProcessor())

        await fake_base.async_input_queue.put(b"raw_frame")
        result = await extended.get_processed_input()
        self.assertEqual(result, b"EXT_raw_frame")

        extended.put_processed_output(b"play_frame")
        fake_base.enqueue_playback.assert_called_once_with(b"OUT_play_frame", generation=7)
        fake_base.c_output_queue.put_nowait.assert_not_called()


if __name__ == "__main__":
    unittest.main()
