"""Validate that model-visible tools preserve current evidence and failures."""
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from core.agent import live_config
from core.config import Config, AgentConfig
from skills import DesktopSkills, SkillError


class SystemInformationWiringTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.skills = DesktopSkills()

    async def test_fresh_query_each_time_and_partial_data_keeps_errors(self):
        answers = [{'status': 'partial', 'observed_at': str(n),
                    'sources': ['/proc/stat'], 'data': {'memory': None},
                    'errors': ['memory unreadable']} for n in (1, 2)]
        with patch('skills.system_information.get_system_information',
                   new=AsyncMock(side_effect=answers)) as query:
            first = await self.skills.execute('get_system_information', {'section': 'memory'})
            second = await self.skills.execute('get_system_information', {'section': 'memory'})
        self.assertNotEqual(first['observed_at'], second['observed_at'])
        self.assertIsNone(second['data']['memory'])
        self.assertEqual(second['errors'], ['memory unreadable'])
        self.assertEqual(query.await_count, 2)

    async def test_controls_preserve_unverified_effects_and_forward_exact_targets(self):
        unverified = {'status': 'dispatched_unverified', 'verified': False,
                      'observed_at': 'now', 'source': 'pactl'}
        with patch('skills.system_extensions.system_control_extension',
                   new=AsyncMock(return_value=unverified)) as control:
            result = await self.skills.execute('system_control_extension', {
                'category': 'audio_output', 'action': 'set_default', 'target': 'exact-device-id'})
        self.assertEqual(result, unverified)
        control.assert_awaited_once_with(category='audio_output', action='set_default',
                                         target='exact-device-id', value=None)

    async def test_theme_setting_reaches_backend_with_name(self):
        with patch('skills.skills.system_control.control_theme', new=AsyncMock(
                return_value={'status': 'success', 'verified': True})) as control:
            await self.skills.execute('control_theme', {'action': 'set', 'theme_name': 'catppuccin'})
        control.assert_awaited_once_with(action='set', theme_name='catppuccin')

    async def test_unavailable_control_status_does_not_become_success(self):
        status = {'status': 'unavailable', 'errors': ['display backend unavailable']}
        with patch('skills.skills.system_control.get_control_status',
                   new=AsyncMock(return_value=status)):
            result = await self.skills.execute('get_system_control_status', {'category': 'display'})
        self.assertEqual(result, status)

    def test_custom_prompt_contains_live_evidence_rules(self):
        cfg = Config(agent=AgentConfig(system_instruction='Personal assistant.'))
        cfg.memory.enabled = False
        instruction = live_config('Aoede', skills=self.skills, config=cfg)['system_instruction']
        self.assertTrue(instruction.startswith('Personal assistant.'))
        self.assertIn('LIVE SYSTEM EVIDENCE RULE', instruction)
        self.assertIn('not CPU utilization', instruction)
        self.assertIn('do not reuse old conversation', instruction)
        self.assertNotIn('LIVE SYSTEM EVIDENCE RULE', live_config('Aoede')['system_instruction'])

    def test_manifest_parameters_match_handlers_and_mirrors(self):
        for name in ('get_system_information', 'get_system_control_status', 'system_control_extension',
                     'control_theme', 'control_notifications', 'open_control_panel'):
            spec = self.skills._skills[name]
            handler = getattr(self.skills, self.skills.ADAPTERS[spec['adapter']])
            parameters = set(inspect.signature(handler).parameters)
            self.assertFalse(set(spec['parameters_json_schema']['properties']) - parameters, name)
        root = Path(__file__).resolve().parents[2]
        for name in ('system-information.json', 'system-extensions.json',
                     'desktop-awareness.json', 'system-controls.json'):
            self.assertEqual(json.loads((root / 'skill_manifests' / name).read_text()),
                             json.loads((root / 'skills/manifests' / name).read_text()), name)
