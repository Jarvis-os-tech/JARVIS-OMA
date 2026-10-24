"""Default autonomous goals to explicit budget routes without touching voice."""
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from skills import DesktopSkills, SkillError


class AgentCostPolicyTests(unittest.IsolatedAsyncioTestCase):
    def make_skills(self):
        skills = DesktopSkills()
        skills._agent_orchestrator.executables = {
            'hermes': '/bin/hermes',
            'opencode': '/bin/opencode',
            'claude': '/bin/claude',
        }
        skills._adapter_delegate_team = AsyncMock(return_value={'team': {'id': 'team-test'}})
        return skills

    async def test_default_goal_fails_closed_before_launch_without_budget_routes(self):
        skills = self.make_skills()

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SkillError, 'JARVIS_BUDGET_MODEL_HERMES'):
                await skills._adapter_start_agent_goal('Build feature', '/workspace')

        skills._adapter_delegate_team.assert_not_awaited()

    async def test_default_goal_uses_explicit_budget_routes(self):
        skills = self.make_skills()
        env = {
            'JARVIS_BUDGET_MODEL_HERMES': 'hermes-small',
            'JARVIS_BUDGET_MODEL_OPENCODE': 'opencode-small',
        }

        with patch.dict(os.environ, env, clear=True):
            result = await skills._adapter_start_agent_goal('Build feature', '/workspace')

        self.assertEqual(result['cost_policy']['profile'], 'budget')
        assignments = skills._adapter_delegate_team.await_args.args[1]
        self.assertEqual(assignments[0]['model'], 'hermes-small')
        self.assertEqual(assignments[1]['model'], 'haiku')
        self.assertEqual(assignments[2]['model'], 'opencode-small')
        self.assertTrue(assignments[2]['batch'])

    async def test_configured_profile_is_explicit_opt_in(self):
        skills = self.make_skills()

        with patch.dict(os.environ, {}, clear=True):
            result = await skills._adapter_start_agent_goal(
                'Build feature', '/workspace', cost_profile='configured')

        self.assertEqual(result['cost_policy']['profile'], 'configured')
        assignments = skills._adapter_delegate_team.await_args.args[1]
        self.assertTrue(all('model' not in assignment for assignment in assignments))

    async def test_direct_delegate_defaults_to_cheap_model(self):
        skills = self.make_skills()
        skills._agent_orchestrator.delegate = MagicMock(
            return_value={'job': {'id': 'job-test'}})

        await skills._adapter_delegate_agent('claude', 'Review', '/workspace')

        self.assertEqual(
            skills._agent_orchestrator.delegate.call_args.kwargs['model'], 'haiku')

    async def test_direct_delegate_missing_route_fails_before_launch(self):
        skills = self.make_skills()
        skills._agent_orchestrator.delegate = MagicMock()

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SkillError, 'JARVIS_BUDGET_MODEL_HERMES'):
                await skills._adapter_delegate_agent('hermes', 'Research', '/workspace')

        skills._agent_orchestrator.delegate.assert_not_called()

    async def test_direct_delegate_explicit_model_overrides_budget_policy(self):
        skills = self.make_skills()
        skills._agent_orchestrator.delegate = MagicMock(
            return_value={'job': {'id': 'job-test'}})

        await skills._adapter_delegate_agent(
            'hermes', 'Research', '/workspace', model='chosen-small')

        self.assertEqual(
            skills._agent_orchestrator.delegate.call_args.kwargs['model'],
            'chosen-small')

    def test_skill_manifest_documents_budget_default_and_configured_opt_in(self):
        skills = DesktopSkills()
        tool = next(item for item in skills._skills.values()
                    if item['name'] == 'start_agent_goal')
        description = tool['parameters_json_schema']['properties']['cost_profile']['description']

        self.assertIn('Defaults to budget', description)
        self.assertIn('Use configured', description)

