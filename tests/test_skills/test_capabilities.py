import unittest
from unittest.mock import patch, AsyncMock

from core.agent import live_config
from core.config import Config, AgentConfig
from skills import DesktopSkills


class CapabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_lookup_routes_to_real_tool_without_executing_it(self):
        skills = DesktopSkills()
        skills._adapter_set_volume = AsyncMock()
        result = await skills.execute('list_capabilities', {'query': 'volume'})
        row = next(c for c in result['capabilities'] if c['name'] == 'set_volume')
        self.assertTrue(row['adapter_implemented'])
        self.assertIn('percent', row['parameters_json_schema']['properties'])
        self.assertFalse(row['runtime_verified'])
        skills._adapter_set_volume.assert_not_awaited()

    async def test_missing_dependencies_remain_visible_in_catalog(self):
        with patch('skills.skills.shutil.which', return_value=None):
            skills = DesktopSkills(exclude_unavailable=True)
            result = await skills.execute('list_capabilities', {'query': 'gui', 'limit': 50})
        row = next(c for c in result['capabilities'] if c['name'] == 'gui_list_windows')
        self.assertFalse(row['available'])
        self.assertFalse(row['exposed'])
        self.assertIn('cua-driver', row['missing_commands'])
        self.assertNotIn('gui_list_windows', skills.capability_context())

    async def test_custom_prompt_still_receives_capability_guidance(self):
        cfg = Config(agent=AgentConfig(system_instruction='You are my personal assistant.'))
        cfg.memory.enabled = False
        skills = DesktopSkills(config=cfg)
        instruction = live_config('Aoede', skills=skills, config=cfg)['system_instruction']
        self.assertTrue(instruction.startswith('You are my personal assistant.'))
        self.assertIn('CAPABILITY CHECK RULE', instruction)
        self.assertIn('list_capabilities', instruction)
        self.assertIn('gui_list_windows', instruction)
        self.assertIn('set_volume', instruction)

    async def test_registered_declarations_have_callable_handlers(self):
        skills = DesktopSkills()
        for spec in skills._skills.values():
            self.assertTrue(callable(getattr(skills, skills.ADAPTERS[spec['adapter']], None)), spec['name'])
        result = await skills.execute('list_capabilities', {'query': '', 'limit': 1})
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['capabilities']), 1)

    async def test_no_tools_does_not_advertise_capabilities(self):
        instruction = live_config('Aoede')['system_instruction']
        self.assertNotIn('CAPABILITY CHECK RULE', instruction)
