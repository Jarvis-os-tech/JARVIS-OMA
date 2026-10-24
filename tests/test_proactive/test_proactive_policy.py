import unittest
from proactive.policy import Action, ActionEffect, DecisionStatus, PolicyLimits, ProactivePolicy

class ProactivePolicyTests(unittest.TestCase):
    def test_invalid_timestamps_do_not_poison_rate_expiry(self):
        action = Action('read', ActionEffect.READ_ONLY)
        for invalid in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(invalid=invalid):
                policy = ProactivePolicy(PolicyLimits(rate_limit_count=1, rate_limit_window=1))
                with self.assertRaises(ValueError):
                    policy.evaluate('first', action, invalid)
                self.assertTrue(policy.evaluate('first', action, 0).allowed)
                with self.assertRaises(ValueError):
                    policy.evaluate('invalid', action, invalid)
                self.assertIs(policy.evaluate('blocked', action, .5).status,
                              DecisionStatus.RATE_LIMITED)
                self.assertTrue(policy.evaluate('later', action, 2).allowed)

    def test_limits_reject_nonfinite_durations_and_invalid_counts(self):
        for field in ('dedupe_window', 'cooldown', 'rate_limit_window'):
            for invalid in (float('nan'), float('inf'), float('-inf'), True, '1'):
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaises((ValueError, TypeError)):
                        PolicyLimits(**{field: invalid})
        for invalid in (True, 1.5, float('nan'), float('inf'), '2'):
            with self.subTest(count=invalid):
                with self.assertRaises((ValueError, TypeError)):
                    PolicyLimits(rate_limit_count=invalid)

    def test_effects(self):
        cases = [(ActionEffect.READ_ONLY, DecisionStatus.ALLOWED),
                 (ActionEffect.LOCAL_REVERSIBLE, DecisionStatus.ALLOWED),
                 (ActionEffect.EXTERNAL, DecisionStatus.APPROVAL_REQUIRED),
                 (ActionEffect.DESTRUCTIVE, DecisionStatus.APPROVAL_REQUIRED),
                 (ActionEffect.UNKNOWN, DecisionStatus.APPROVAL_REQUIRED)]
        for effect, expected in cases:
            with self.subTest(effect=effect):
                self.assertIs(ProactivePolicy().evaluate('t', Action('a', effect), 1).status, expected)

    def test_duplicate_cooldown_rate_and_pause(self):
        action = Action('read', ActionEffect.READ_ONLY)
        policy = ProactivePolicy(PolicyLimits(dedupe_window=2, cooldown=8, rate_limit_count=2))
        self.assertTrue(policy.evaluate('a', action, 0).allowed)
        self.assertIs(policy.evaluate('a', action, 1).status, DecisionStatus.DUPLICATE)
        self.assertIs(policy.evaluate('a', action, 3).status, DecisionStatus.COOLDOWN)
        policy.pause(); self.assertIs(policy.evaluate('b', action, 4).status, DecisionStatus.PAUSED)
        policy.resume(); self.assertTrue(policy.evaluate('b', action, 8).allowed)
        self.assertIs(policy.evaluate('c', action, 9).status, DecisionStatus.RATE_LIMITED)

    def test_invalid(self):
        with self.assertRaises(ValueError): PolicyLimits(rate_limit_count=0)
        with self.assertRaises(ValueError): ProactivePolicy().evaluate(' ', Action('x'), 0)
        with self.assertRaises(TypeError): ProactivePolicy().evaluate('x', Action('x'), True)

if __name__ == '__main__': unittest.main()
