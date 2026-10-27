"""Clock-controlled notice policy checks; no audio, provider or desktop needed."""
import math
import unittest

from proactive.attention import AttentionPolicy


class AttentionPolicyTests(unittest.TestCase):
    def test_first_notice_is_immediate_without_invented_recent_activity(self):
        policy = AttentionPolicy()
        self.assertTrue(policy.can_deliver(0))

    def test_waits_for_quiet_after_both_user_and_assistant_activity(self):
        policy = AttentionPolicy(quiet_seconds=2)
        policy.note_activity(10)
        self.assertFalse(policy.can_deliver(11.999))
        policy.note_activity(11.5)
        self.assertFalse(policy.can_deliver(13))
        self.assertTrue(policy.can_deliver(13.5))

    def test_busy_mute_and_standby_each_block_otherwise_eligible_delivery(self):
        policy = AttentionPolicy()
        for flag in ('busy', 'muted', 'standby'):
            with self.subTest(flag=flag):
                self.assertFalse(policy.can_deliver(100, **{flag: True}))
        self.assertTrue(policy.can_deliver(100))

    def test_failed_attempts_do_not_consume_the_successful_send_cooldown(self):
        policy = AttentionPolicy(cooldown_seconds=30)
        self.assertTrue(policy.can_deliver(5))
        self.assertTrue(policy.can_deliver(6))
        policy.delivered(6)
        self.assertFalse(policy.can_deliver(35.999))
        self.assertTrue(policy.can_deliver(36))

    def test_quiet_and_cooldown_both_have_to_expire(self):
        policy = AttentionPolicy(quiet_seconds=2, cooldown_seconds=30)
        policy.delivered(10)
        policy.note_activity(39)
        self.assertFalse(policy.can_deliver(40))
        self.assertTrue(policy.can_deliver(41))

    def test_duplicate_event_revision_is_suppressed_without_refreshing_window(self):
        policy = AttentionPolicy(dedupe_seconds=300)
        self.assertTrue(policy.admit('calendar:event:start-1', 0))
        self.assertFalse(policy.admit('calendar:event:start-1', 200))
        self.assertTrue(policy.admit('calendar:event:start-2', 200))
        self.assertFalse(policy.admit('calendar:event:start-1', 299.999))
        self.assertTrue(policy.admit('calendar:event:start-1', 300))

    def test_key_storage_is_bounded_and_unkeyed_notices_bypass_dedupe(self):
        policy = AttentionPolicy(max_keys=2)
        self.assertTrue(policy.admit('first', 0))
        self.assertTrue(policy.admit('second', 1))
        self.assertTrue(policy.admit('third', 2))
        self.assertFalse(policy.admit('second', 3))
        self.assertTrue(policy.admit('first', 3))
        self.assertTrue(policy.admit(None, 3))
        self.assertTrue(policy.admit(None, 3))

    def test_older_callback_timestamp_cannot_shorten_quiet_or_cooldown(self):
        policy = AttentionPolicy(quiet_seconds=2, cooldown_seconds=30)
        policy.note_activity(10)
        policy.note_activity(2)
        self.assertFalse(policy.can_deliver(11))
        policy.delivered(10)
        policy.delivered(2)
        self.assertFalse(policy.can_deliver(39))
        self.assertTrue(policy.can_deliver(40))

    def test_zero_quiet_cooldown_and_dedupe_windows_are_explicitly_supported(self):
        policy = AttentionPolicy(quiet_seconds=0, cooldown_seconds=0, dedupe_seconds=0)
        policy.note_activity(10)
        policy.delivered(10)
        self.assertTrue(policy.can_deliver(10))
        self.assertTrue(policy.admit('event', 10))
        self.assertTrue(policy.admit('event', 10))
        self.assertFalse(policy.can_deliver(10, muted=True))

    def test_invalid_configuration_times_and_identifiers_fail_clearly(self):
        for field in ('quiet_seconds', 'cooldown_seconds', 'dedupe_seconds'):
            for value in (-1, math.inf, math.nan, True, '2'):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    AttentionPolicy(**{field: value})
        for value in (0, -1, True, 1.5):
            with self.subTest(max_keys=value), self.assertRaises(ValueError):
                AttentionPolicy(max_keys=value)
        policy = AttentionPolicy()
        for value in (-1, math.inf, math.nan, True, '2'):
            for method in (policy.note_activity, policy.can_deliver, policy.delivered):
                with self.subTest(time=value, method=method), self.assertRaises(ValueError):
                    method(value)
        for key in ('', ' ', 'a' * 513, '\N{SNOWMAN}' * 171, 1):
            with self.subTest(key=key), self.assertRaises(ValueError):
                policy.admit(key, 0)
