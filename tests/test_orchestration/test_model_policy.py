import unittest
from orchestration.model_policy import apply_model_policy


class ModelPolicyTests(unittest.TestCase):
    def test_missing_budget_route_fails_without_default_model_fallback(self):
        with self.assertRaisesRegex(ValueError, 'JARVIS_BUDGET_MODEL_HERMES'):
            apply_model_policy([{'agent': 'hermes'}], environ={})

    def test_models_are_explicit_and_input_is_unchanged(self):
        assignments = [{'agent': 'codex'}, {'agent': 'hermes'}]
        result = apply_model_policy(assignments, environ={'JARVIS_BUDGET_MODEL_HERMES': 'provider/small'})
        self.assertEqual(result[0]['model'], 'gpt-5.6-luna')
        self.assertEqual(result[1]['model'], 'provider/small')
        self.assertNotIn('model', assignments[0])

    def test_budget_opencode_uses_model_capable_batch_route(self):
        assignments = [{'agent': 'opencode', 'visible': True, 'batch': False}]
        result = apply_model_policy(
            assignments, environ={'JARVIS_BUDGET_MODEL_OPENCODE': 'provider/small'})

        self.assertEqual(result[0]['model'], 'provider/small')
        self.assertTrue(result[0]['batch'])
        self.assertFalse(assignments[0]['batch'])

    def test_configured_mode_preserves_native_defaults(self):
        self.assertEqual(apply_model_policy([{'agent': 'hermes'}], 'configured', {}), [{'agent': 'hermes'}])

    def test_invalid_model_rejected(self):
        with self.assertRaises(ValueError):
            apply_model_policy([{'agent': 'codex'}], environ={'JARVIS_BUDGET_MODEL_CODEX': '--bad'})
