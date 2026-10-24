from learning.evidence import EpisodeStore, sanitize
from learning.voice_tests import checklist, evidence_report
from learning.voice_tests import record_result, timing_summary
import pytest


def test_voice_report_matches_fragments_without_awarding_pass(tmp_path):
    store = EpisodeStore(tmp_path)
    store.append('one', 'started', sanitize({'model': 'test'}))
    store.append('one', 'user_input', sanitize({'text': 'Voice check re'}))
    store.append('one', 'user_input', sanitize({'text': 'search. Find documentation.'}))
    store.append('one', 'action_started', sanitize({'tool': 'internet_search'}))
    store.append('one', 'assistant_output', sanitize({'text': 'An unverified answer.'}))
    store.append('one', 'ended', sanitize({'state': 'delivered_unverified'}))
    report = evidence_report(store)
    research = next(case for case in report['tests'] if case['id'] == 'research')
    assert research['manual_result'] == 'pending'
    assert research['matches'][0]['tools'] == ['internet_search']
    assert research['matches'][0]['assistant_output_captured']
    assert research['matches'][0]['end']['state'] == 'delivered_unverified'
    assert not report['tests'][0]['matches']


def test_empty_voice_report_and_unique_checklist(tmp_path):
    report = evidence_report(EpisodeStore(tmp_path))
    assert len(checklist()) == len({case['id'] for case in checklist()}) == 6
    assert all(case['manual_result'] == 'pending' and not case['matches'] for case in report['tests'])


def test_review_preserves_human_attribution_and_latest_result(tmp_path):
    store = EpisodeStore(tmp_path)
    store.append('one', 'started', sanitize({'model': 'test'}))
    store.append('one', 'user_input', sanitize({'text': 'Voice check hello'}))
    record_result(store, 'one', 'partial', lag='before_answer', note='Long pause')
    record_result(store, 'one', 'pass', lag='during_speech', note='Answer correct, speech paused')
    case = evidence_report(store)['tests'][0]
    assert case['manual_result'] == 'pass'
    assert case['matches'][0]['manual_review']['authority'] == 'user'
    assert case['matches'][0]['manual_review']['diagnosis'] == 'unknown'
    assert len([e for e in store.read('one') if e['kind'] == 'manual_review']) == 2
    with pytest.raises(ValueError, match='Unknown episode'):
        record_result(store, 'absent', 'pass')
    with pytest.raises(ValueError):
        record_result(store, 'one', 'automatic_pass')
    with pytest.raises(ValueError):
        record_result(store, 'one', 'pass', lag='fixed')


def test_timing_missing_and_out_of_order_remain_unknown():
    def event(kind, at, data=None):
        return {'kind': kind, 'observed_at': at, 'payload': sanitize(data or {})}
    assert timing_summary([])['last_input_to_first_output_event_ms'] is None
    events = [event('user_input', 10), event('assistant_output', 10.25),
              event('action_returned', 10.3, {'call_id': 'a', 'elapsed_ms': 120})]
    assert timing_summary(events)['last_input_to_first_output_event_ms'] == 250
    assert timing_summary(events)['tool_durations'] == [{'call_id': 'a', 'elapsed_ms': 120}]
    events[0]['observed_at'] = 11
    assert timing_summary(events)['last_input_to_first_output_event_ms'] is None
