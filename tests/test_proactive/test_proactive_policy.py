import unittest
from proactive.policy import Action, ActionEffect, DecisionStatus, PolicyLimits, ProactivePolicy

class ProactivePolicyTests(unittest.TestCase):
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
