"""Deterministic speech turn gating; no model, cloud service, or audio device."""
import unittest

from core.speech_turn import SpeechTurnGate, SileroSpeechDetector
from unittest.mock import Mock, patch


FRAME = b"\x00\x10" * 320
QUIET = bytes(640)


class SpeechTurnGateTests(unittest.TestCase):
    def test_detector_preserves_samples_in_recommended_nonoverlapping_windows(self):
        import numpy as np
        model = Mock()
        model.predict.return_value = .8
        with patch('openwakeword.vad.VAD', return_value=model):
            detector = SileroSpeechDetector()
        frames = [np.arange(i * 320, (i + 1) * 320, dtype='<i2') for i in range(3)]
        scores = [detector(frame.tobytes()) for frame in frames]
        self.assertEqual(scores, [0.0, .8, .8])
        calls = model.predict.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call.kwargs['frame_size'] == 480 for call in calls))
        np.testing.assert_array_equal(np.concatenate([call.args[0] for call in calls]),
                                      np.arange(960, dtype='<i2'))

    def test_detector_reset_drops_partial_old_audio_and_cached_score(self):
        import numpy as np
        model = Mock()
        model.predict.return_value = .9
        with patch('openwakeword.vad.VAD', return_value=model):
            detector = SileroSpeechDetector()
        self.assertEqual(detector(FRAME), 0.0)
        self.assertEqual(detector(FRAME), .9)
        self.assertEqual(detector(FRAME), .9)
        self.assertEqual(detector(FRAME), .9)
        self.assertFalse(detector.fresh_prediction)
        detector.reset()
        self.assertEqual(detector(QUIET), 0.0)
        self.assertEqual(detector(QUIET), .9)
        np.testing.assert_array_equal(model.predict.call_args.args[0], np.zeros(480, dtype='<i2'))
        model.reset_states.assert_called_once()

    def test_one_model_positive_is_not_counted_twice_while_next_window_fills(self):
        model = Mock()
        model.predict.side_effect = [.1, .9, .1]
        with patch('openwakeword.vad.VAD', return_value=model):
            gate = SpeechTurnGate(detector=SileroSpeechDetector())
        # Third input gives one positive; fourth merely repeats that cached score.
        results = [gate.process(FRAME, now=i * .02) for i in range(5)]
        self.assertFalse(any(result.opened for result in results))

    def test_short_moderate_confidence_phrase_can_open_a_turn(self):
        gate = SpeechTurnGate(detector=lambda pcm: .55)
        self.assertFalse(gate.process(FRAME, now=0).opened)
        self.assertTrue(gate.process(FRAME, now=.02).opened)

    def test_noisy_continuation_stays_one_turn_but_cannot_start_a_new_turn(self):
        scores = iter([.3] * 25 + [.9, .9] + [.3] * 25)
        gate = SpeechTurnGate(detector=lambda _: next(scores), silence_frames=20)
        for index in range(25):
            self.assertFalse(gate.process(FRAME, now=index * .02).opened)
        self.assertFalse(gate.active)
        gate.process(FRAME, now=.5)
        self.assertTrue(gate.process(FRAME, now=.52).opened)
        for index in range(25):
            self.assertFalse(gate.process(FRAME, now=.54 + index * .02).closed)
        self.assertTrue(gate.active)
        for index in range(20):
            result = gate.process(QUIET, now=1.04 + index * .02)
        self.assertTrue(result.closed)
        self.assertEqual(gate.accepted_turns, 1)

    def test_raw_silence_stays_zero_even_when_detector_is_confident(self):
        calls = []

        def detector(pcm):
            calls.append(pcm)
            return 0.99

        gate = SpeechTurnGate(detector=detector)
        for index in range(8):
            result = gate.process(QUIET, now=index * 0.02)
            self.assertEqual(result.pcm, QUIET)
            self.assertFalse(result.opened)
        self.assertFalse(gate.active)
        self.assertEqual(gate.accepted_turns, 0)

    def test_requires_trigger_frames_and_opens_with_bounded_preroll(self):
        gate = SpeechTurnGate(detector=lambda pcm: 0.95, trigger_frames=3)
        results = [gate.process(FRAME, now=i * 0.02) for i in range(3)]

        self.assertEqual([item.opened for item in results], [False, False, True])
        self.assertTrue(gate.active)
        self.assertEqual(gate.accepted_turns, 1)
        self.assertEqual(results[-1].pcm, FRAME * 3)
        self.assertNotEqual(results[-1].pcm, QUIET)

    def test_blocked_frames_are_silenced_and_cannot_open(self):
        gate = SpeechTurnGate(detector=lambda pcm: 0.99, trigger_frames=1)
        for index in range(5):
            result = gate.process(FRAME, now=index * 0.02, blocked=True)
            self.assertEqual(result.pcm, QUIET)
            self.assertFalse(result.opened)
        self.assertFalse(gate.active)
        self.assertEqual(gate.accepted_turns, 0)
        self.assertEqual(gate.suppressed_frames, 5)

    def test_block_requires_quiet_tail_before_speech_can_open(self):
        gate = SpeechTurnGate(detector=lambda pcm: 0.95, trigger_frames=1, tail_seconds=0.45)
        blocked = gate.process(FRAME, now=0.0, blocked=True)
        self.assertEqual(blocked.pcm, QUIET)

        for i in range(1, 23):  # 0.44 seconds of quiet is short of the required tail.
            result = gate.process(QUIET, now=i * 0.02)
            self.assertFalse(result.opened)
            self.assertEqual(result.pcm, QUIET)
        early = gate.process(FRAME, now=0.44)
        self.assertFalse(early.opened)
        self.assertEqual(early.pcm, QUIET)

        ready = gate.process(FRAME, now=0.46)
        self.assertTrue(ready.opened)
        self.assertTrue(gate.active)
        self.assertEqual(gate.accepted_turns, 1)

    def test_active_turn_closes_after_configured_silence_frames(self):
        gate = SpeechTurnGate(detector=lambda pcm: 0.95, trigger_frames=1, silence_frames=30)
        opened = gate.process(FRAME, now=0.0)
        self.assertTrue(opened.opened)

        results = [gate.process(QUIET, now=(i + 1) * 0.02) for i in range(30)]
        self.assertTrue(all(item.pcm == QUIET for item in results))
        self.assertFalse(gate.active)
        self.assertTrue(results[-1].closed)
        self.assertEqual(gate.accepted_turns, 1)


if __name__ == "__main__":
    unittest.main()
