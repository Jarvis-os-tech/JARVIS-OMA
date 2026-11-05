"""Original-text and typed-value contracts for the English parsing pilot."""
import asyncio
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from jarvis_control.command_values import number_slots, parse_values
from jarvis_control.nlu import IntentCategory, NLUEngine
from jarvis_control.parsing_service import parse_command_values
from voice_layer.local_speech import command_for

CASES = json.loads(Path(__file__).with_name('parsing_cases.json').read_text())['cases']
ANCHOR = datetime(2026, 11, 3, 23, 45, tzinfo=ZoneInfo('Asia/Kolkata'))


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_golden_local_control_commands(case):
    actual = command_for(case['text'], {})
    assert (list(actual) if actual else None) == case['expected']


def test_values_keep_unicode_offsets_signs_fractions_and_multiple_values():
    raw = '🙂 minus five, forty point five and one half, zero'
    slots = number_slots(raw)
    assert [s['value'] for s in slots] == [-5, 40.5, .5, 0]
    assert all(raw[s['start']:s['end']] == s['surface'] for s in slots)


@pytest.mark.parametrize('raw', [
    'Type "java  forty five"', 'Type `java twenty`', "Type 'java forty'",
    'open /tmp/java/forty.txt', 'open ~/Downloads/twenty.txt',
    'Read https://example.test/forty/20', 'inspect build42 and report_20.txt',
    'Type “java  forty”', 'Type "java  forty',
])
def test_protected_content_is_never_rewritten_or_extracted(raw):
    assert NLUEngine.normalize_text(raw) == raw
    assert number_slots(raw) == []


def test_quoted_instructions_cannot_trigger_standby_or_pairing():
    for text in ['Type "go to sleep"', 'Type "pair my phone"', 'Explain `enter standby`']:
        assert NLUEngine.analyze(text).category not in {IntentCategory.STANDBY, IntentCategory.PHONE_PAIRING}
        assert not NLUEngine.validate_tool_intent('enter_standby', {}, text)[0]


def test_nlu_exposes_control_evidence_without_rewriting_words():
    raw = 'set volume to forty five percent'
    result = NLUEngine.analyze(raw)
    assert result.raw_text == result.normalized_text == raw
    assert result.entities['control_arguments'] == {'action': 'volume_set', 'value': 45}
    assert result.entities['values'][0]['surface'] == 'forty five'


@pytest.mark.parametrize('tool,args,text,allowed', [
    ('set_volume', {'percent':45}, 'set volume to forty five percent', True),
    ('set_volume', {'percent':40}, 'set volume to forty five percent', False),
    ('set_brightness', {'percent':45}, 'set volume to forty five percent', False),
    ('system_control', {'action':'volume_set','value':45}, 'set volume to forty five percent', True),
    ('system_control', {'action':'volume_adjust','value':45}, 'set volume to forty five percent', False),
    ('set_volume', {'percent':5}, 'set volume to minus five', False),
    ('set_volume', {'percent':40}, 'set volume to thirty or forty', False),
    ('set_volume', {'percent':40}, 'Could you set volume to thirty or forty?', False),
    ('set_volume', {'percent':40}, 'set volume to forty point five', False),
    ('set_volume', {'percent':100}, 'set volume to one hundred and five', False),
    ('switch_workspace', {'workspace':2}, 'switch to workspace two', True),
    ('switch_workspace', {'workspace':3}, 'switch to workspace two', False),
])
def test_model_arguments_must_match_spoken_control_value(tool, args, text, allowed):
    assert NLUEngine.validate_tool_intent(tool, args, text)[0] is allowed


@pytest.mark.asyncio
async def test_registry_executes_read_only_parser_with_original_text():
    from skills.skills import DesktopSkills
    registry = DesktopSkills()
    try:
        result = await registry.execute('parse_command_values', {
            'text': 'tomorrow at five pm', 'anchor_datetime': ANCHOR.isoformat()})
        assert result['raw_text'] == 'tomorrow at five pm' and result['candidate_only']
        assert result['values'][-1]['value'] == '2026-11-04T17:00:00+05:30'
    finally:
        await registry.close_agent_jobs()


@pytest.mark.parametrize('text,expected,seconds', [
    ('tomorrow at five pm', '2026-11-04T17:00:00+05:30', None),
    ('in thirty minutes', '2026-11-04T00:15:00+05:30', 1800),
    ('in two hours and thirty minutes', '2026-11-04T02:15:00+05:30', 9000),
    ('tomorrow at 17:30', '2026-11-04T17:30:00+05:30', None),
    ('2026-11-04T17:30:00+05:30', '2026-11-04T17:30:00+05:30', None),
])
def test_temporal_values_use_explicit_anchor_and_dedupe_spans(text, expected, seconds):
    result = parse_values(text, include_temporal=True, anchor=ANCHOR)
    assert result['status'] == 'ok' and not result['requires_clarification']
    assert [s['value'] for s in result['values'] if s['kind'] == 'datetime'] == [expected]
    durations = [s['value'] for s in result['values'] if s['kind'] == 'duration']
    assert durations == ([] if seconds is None else [seconds])
    assert all(text[s['start']:s['end']] == s['surface'] for s in result['values'])
    assert result['candidate_only'] is True


@pytest.mark.parametrize('text', ['at five', 'at 5:30', 'tomorrow', 'at 5 pm PST',
                                   'at 5 pm pst', 'at 5 pm CST', 'at 5 pm eastern', 'on 04/05/2026'])
def test_temporal_ambiguity_requires_clarification(text):
    assert parse_values(text, include_temporal=True, anchor=ANCHOR)['requires_clarification']


@pytest.mark.parametrize('text', ['2026-11-01T01:30:00', '2026-03-08T02:30:00'])
def test_dst_fold_or_gap_is_rejected(text):
    result = parse_values(text, include_temporal=True, anchor=ANCHOR, time_zone='America/New_York')
    assert result['status'] == 'invalid_parse' and result['requires_clarification']


@pytest.mark.parametrize('anchor,expected', [
    ('2026-11-01T00:30:00-04:00', '2026-11-01T01:30:00-05:00'),
    ('2026-03-08T01:30:00-05:00', '2026-03-08T04:30:00-04:00'),
])
def test_relative_durations_count_elapsed_seconds_across_dst(anchor, expected):
    result = parse_values('in two hours', include_temporal=True,
                          anchor=datetime.fromisoformat(anchor), time_zone='America/New_York')
    assert not result['requires_clarification']
    assert [s['value'] for s in result['values'] if s['kind'] == 'datetime'] == [expected]


@pytest.mark.asyncio
async def test_transcription_chunks_keep_verbatim_user_evidence():
    from voice_layer.daemon import LiveVoice
    from voice_layer.playback import Playback
    voice = LiveVoice(Playback('test'), skills=NS(declarations=[]))
    voice._reply_authorized = True
    chunks = ['Type "java ', ' forty" and open /tmp/java/forty.txt']
    for chunk in chunks:
        await voice.handle(NS(server_content=NS(input_transcription=NS(text=chunk))))
    assert voice._user_text == ''.join(chunks)
    assert voice._memory_user == ''.join(chunks)


def test_unsupported_language_missing_dependency_and_no_match_differ(monkeypatch):
    assert parse_values('hello')['status'] == 'no_match'
    assert parse_values('forty', language='hi-IN')['status'] == 'unsupported_language'
    assert parse_values('tomorrow', include_temporal=True)['status'] == 'invalid_parse'
    def unavailable(*a, **kw):
        raise ImportError('synthetic missing dependency')
    monkeypatch.setattr('jarvis_control.command_values.number_slots', unavailable)
    assert parse_values('forty')['status'] == 'dependency_unavailable'


@pytest.mark.asyncio
async def test_temporal_tool_runs_worker_with_fixed_anchor():
    result = await parse_command_values('tomorrow at five pm', anchor_datetime=ANCHOR.isoformat())
    assert result['status'] == 'ok'
    assert [s['value'] for s in result['values'] if s['kind'] == 'datetime'] == ['2026-11-04T17:00:00+05:30']


@pytest.mark.asyncio
async def test_cancelled_parser_is_killed_and_reaped(monkeypatch):
    started = asyncio.Event()
    killed = False
    async def communicate(*a):
        if killed:
            return b'', b''
        started.set()
        await asyncio.Event().wait()
    def kill():
        nonlocal killed
        killed = True
    process = NS(returncode=None, communicate=AsyncMock(side_effect=communicate), kill=kill)
    monkeypatch.setattr('asyncio.create_subprocess_exec', AsyncMock(return_value=process))
    task = asyncio.create_task(parse_command_values('tomorrow at five pm'))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert killed and process.communicate.await_count == 2


@pytest.mark.asyncio
async def test_timed_out_parser_is_killed_and_cannot_report_success(monkeypatch):
    killed = []
    process = NS(returncode=None, communicate=AsyncMock(return_value=(b'', b'')),
                 kill=lambda: killed.append(True))
    monkeypatch.setattr('asyncio.create_subprocess_exec', AsyncMock(return_value=process))
    async def expired(coroutine, timeout):
        coroutine.close()
        raise asyncio.TimeoutError
    monkeypatch.setattr('asyncio.wait_for', expired)
    result = await parse_command_values('tomorrow at five pm')
    assert result['status'] == 'parser_timeout' and result['values'] == []
    assert killed and process.communicate.await_count == 1


@pytest.mark.asyncio
async def test_invalid_anchor_is_rejected_before_starting_worker(monkeypatch):
    spawn = AsyncMock()
    monkeypatch.setattr('asyncio.create_subprocess_exec', spawn)
    result = await parse_command_values('tomorrow at five pm', anchor_datetime='2026-11-03T23:45:00')
    assert result['status'] == 'invalid_anchor_or_timezone'
    spawn.assert_not_awaited()


def test_parsing_tool_is_registered_read_only_and_not_action_evidence():
    from skills.skills import DesktopSkills
    from orchestration.tool_tiers import CORE_TOOLS, META_TOOLS
    from jarvis_control.evidence import META_TOOLS as EVIDENCE_META_TOOLS
    registry = DesktopSkills.__new__(DesktopSkills)
    registry.manifest_dirs = [Path(__file__).resolve().parents[2] / 'skill_manifests']
    specs = registry._load_manifests()
    assert specs['parse_command_values']['adapter'] == 'parsing.values'
    assert 'parse_command_values' in CORE_TOOLS & META_TOOLS
    assert 'parse_command_values' in EVIDENCE_META_TOOLS
