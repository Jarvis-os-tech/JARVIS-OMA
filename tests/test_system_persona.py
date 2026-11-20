"""OS identity and evidence routes, without performing desktop actions."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from google.genai import types

from voice_layer.daemon import build_instruction, live_config
from voice_layer.persona import system_persona
from orchestration.model_routes import ModelJobs
from orchestration.tool_tiers import CORE_TOOLS


def test_widget_and_reasoning_routes_are_available_only_when_attached():
    basic = build_instruction(['set_volume'])
    assert 'GENERATED WIDGETS ARE PART OF THE OS' not in basic
    assert 'DEEP ANALYSIS ROUTE' not in basic
    richer = build_instruction(['show_widget', 'widget_schema', 'start_model_processing'])
    assert 'GENERATED WIDGETS ARE PART OF THE OS' in richer
    assert 'route=reasoning' in richer
    discovered = build_instruction(['discover_domain_tools', 'execute_domain_tool'])
    assert 'through execute_domain_tool' in discovered
    assert {'start_model_processing', 'model_processing_status'} <= CORE_TOOLS


def test_capability_status_counts_distinct_tools_and_does_not_invent_agents():
    prompt = build_instruction(['set_volume', 'set_volume', 'read_file'])
    assert 'CURRENT ATTACHED OS TOOLS (2 available): set_volume, read_file' in prompt
    assert '279+' not in prompt
    assert 'REASONING ALOUD' not in prompt
    assert 'NEVER pause, freeze, or hold replies' not in prompt


def test_disabled_memory_does_not_read_or_inject_context():
    skills = NS(memory_context=Mock(return_value='private-test-fixture'))
    config = NS(memory=NS(enabled=False), model='gemini-3.8-live')
    prompt = live_config(skills=skills, config=config, memory_context='private-test-fixture')['system_instruction']
    skills.memory_context.assert_not_called()
    assert 'private-test-fixture' not in prompt


@pytest.mark.parametrize('model,expected', [
    ('gemini-3.8-live', None), ('models/gemini-3.8-live', None),
    ('gemini-2.5-flash-native-audio-preview-12-2025', {'thinking_budget': 0}),
])
def test_live_setup_preserves_model_protocol_and_voice(model, expected):
    payload = live_config(config=NS(model=model), voice='Aoede')
    assert payload.get('thinking_config') == expected
    validated = types.LiveConnectConfig.model_validate(payload)
    assert validated.speech_config.voice_config.prebuilt_voice_config.voice_name == 'Aoede'


def test_linkedin_department_routing_does_not_require_hermes():
    prompt = system_persona({'discover_domain_tools', 'execute_domain_tool'})
    assert 'The LinkedIn Department owns requests to work on LinkedIn' in prompt
    assert 'discover the linkedin domain' in prompt
    assert 'Use API Anything for operations on online services other than LinkedIn and\nGoogle Workspace' in prompt
    assert 'Google Workspace Department' in prompt


def test_system_contract_uses_evidence_and_scoped_execution():
    prompt = system_persona()
    for rule in ('system voice and interaction layer', 'Think privately',
                 'Memory supplies preferences/history, not live state',
                 'Do not blindly repeat an uncertain mutation',
                 'discussion alone does not authorize changes'):
        assert rule in prompt


@pytest.mark.asyncio
async def test_reasoning_job_preserves_evidence_and_reports_completion():
    calls = []
    async def generate(model, prompt):
        calls.append((model, prompt))
        return 'The log indicates a timeout; inspect service status before changing settings.'
    events = asyncio.Queue(maxsize=4)
    jobs = ModelJobs(['synthetic-key'], events, generate=generate)
    try:
        receipt = jobs.start('Observed: one network timeout. Goal: diagnose without changes.', 'reasoning')
        assert receipt['status'] == 'queued'
        completed = await asyncio.wait_for(events.get(), 2)
        assert completed['status'] == 'completed'
        assert 'Observed: one network timeout' in calls[0][1]
        assert 'inspect service status' in completed['result']
        assert not jobs.workers
    finally:
        await jobs.close()
