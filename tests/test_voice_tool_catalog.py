import json

import pytest

from jarvis_control.config import Config
from jarvis_control.skills import ControlSkills, UnifiedSkills
from jarvis_voice.daemon import build_instruction
from skills.skills import DesktopSkills


@pytest.mark.asyncio
async def test_voice_catalog_keeps_native_controls_and_specialist_discovery():
    control = ControlSkills(Config())
    desktop = DesktopSkills()
    skills = UnifiedSkills(control_skills=control, desktop_skills=desktop)
    try:
        names = {tool['name'] for tool in skills.live_declarations}
        assert {'system_control', 'launch_app', 'hypr_query', 'send_shortcut',
                'enter_standby', 'discover_domain_tools', 'execute_domain_tool'} <= names
        assert len(skills.live_declarations) < len(skills.declarations)
        assert len(json.dumps(skills.live_declarations)) < len(json.dumps(skills.declarations)) * .65
        assert 'github_connection_status' in {tool['name'] for tool in skills.declarations}
        result = await skills.execute('discover_domain_tools', {'domain': 'github'})
        assert any(item['name'] == 'github_connection_status' for item in json.loads(result)['tools'])
        prompt = build_instruction([{'function_declarations': skills.live_declarations}])
        assert 'SPECIALIST CAPABILITIES' in prompt
        assert 'Do not perform discovery for an already attached everyday control' in prompt
    finally:
        await skills.close_agent_jobs()
