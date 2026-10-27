"""Deterministic response observations; no audio devices or provider required."""
import unittest

from core.response_metrics import ResponseMetrics


class ResponseMetricTests(unittest.TestCase):
    def test_first_pcm_and_tool_use_latest_input_observation(self):
        clock = [1.0]
        metrics = ResponseMetrics(clock=lambda: clock[0])
        metrics.recognized_input()
        clock[0] = 1.2
        metrics.recognized_input()
        clock[0] = 1.25
        metrics.tool_started()
        clock[0] = 1.3
        metrics.audio_received()
        clock[0] = 2.0
        metrics.tool_started()
        metrics.audio_received()
        result = metrics.snapshot()
        self.assertEqual(result['response_first_tool_ms'], 50)
        self.assertEqual(result['response_first_audio_ms'], 100)
        self.assertEqual(result['response_first_audio_samples'], 1)

    def test_greetings_and_unprompted_audio_do_not_create_response_samples(self):
        metrics = ResponseMetrics()
        metrics.audio_received(2)
        metrics.tool_started(3)
        result = metrics.snapshot()
        self.assertEqual(result['response_first_audio_samples'], 0)
        self.assertIsNone(result['response_first_audio_p50_ms'])
        self.assertIsNone(result['response_first_tool_ms'])

    def test_samples_are_bounded_and_percentiles_use_only_retained_values(self):
        metrics = ResponseMetrics(capacity=2)
        for milliseconds in (10, 20, 30):
            metrics.recognized_input(1)
            metrics.audio_received(1 + milliseconds / 1000)
        result = metrics.snapshot()
        self.assertEqual(result['response_first_audio_samples'], 2)
        self.assertEqual(result['response_first_audio_p50_ms'], 25)
        self.assertEqual(result['response_first_audio_p95_ms'], 29.5)

    def test_interruption_and_reconnection_cannot_match_stale_input_to_new_audio(self):
        metrics = ResponseMetrics()
        metrics.recognized_input(1)
        metrics.audio_received(1.1)
        metrics.interrupted()
        metrics.audio_received(3)
        self.assertEqual(metrics.snapshot()['response_first_audio_samples'], 1)
        self.assertIsNone(metrics.snapshot()['response_first_audio_ms'])
        metrics.recognized_input(4)
        metrics.reset()
        metrics.audio_received(5)
        self.assertEqual(metrics.snapshot()['response_first_audio_samples'], 1)

    def test_out_of_order_timestamps_never_report_negative_latency(self):
        metrics = ResponseMetrics()
        metrics.recognized_input(2)
        metrics.tool_started(1)
        metrics.audio_received(1)
        self.assertEqual(metrics.snapshot()['response_first_audio_samples'], 0)
        self.assertIsNone(metrics.snapshot()['response_first_tool_ms'])
        metrics.audio_received(2)
        self.assertEqual(metrics.snapshot()['response_first_audio_ms'], 0)
        self.assertEqual(metrics.snapshot()['response_first_audio_samples'], 1)

    def test_capacity_must_be_a_positive_integer(self):
        for invalid in (True, 0, -1, 1.5):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ResponseMetrics(capacity=invalid)
