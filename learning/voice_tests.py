"""Manual voice checklist and capture report; no automatic quality verdict."""
import re
import math


def record_result(store, episode, result, *, lag='none', note=''):
    from .evidence import sanitize
    if result not in {'pass', 'fail', 'partial'}:
        raise ValueError('Result must be pass, fail, or partial')
    if lag not in {'none', 'before_answer', 'during_speech', 'unknown'}:
        raise ValueError('Invalid lag category')
    if not store.read(episode):
        raise ValueError('Unknown episode')
    store.append(episode, 'manual_review', sanitize({
        'result': result, 'lag': lag, 'note': note,
        'authority': 'user', 'diagnosis': 'unknown'}))
    return {'episode': episode, 'result': result, 'lag': lag, 'authority': 'user'}


def timing_summary(events):
    inputs = [e for e in events if e['kind'] == 'user_input']
    outputs = [e for e in events if e['kind'] == 'assistant_output']
    delay = None
    if inputs and outputs:
        milliseconds = (outputs[0]['observed_at'] - inputs[-1]['observed_at']) * 1000
        if math.isfinite(milliseconds) and milliseconds >= 0:
            delay = round(milliseconds, 1)
    tools = []
    for event in events:
        if event['kind'] == 'action_returned':
            data = event['payload'].get('data', {})
            tools.append({'call_id': data.get('call_id'), 'elapsed_ms': data.get('elapsed_ms')})
    return {'last_input_to_first_output_event_ms': delay, 'tool_durations': tools,
            'limitation': 'Background persistence timestamps are approximate; not acoustic latency. Cause unknown.'}

CASES = (
    ('hello', 'Voice check hello. Tell me what you can help me with in two sentences.', 'Clear audible answer without unnecessary tool actions.'),
    ('research', 'Voice check research. Search the web for the official Python documentation. Tell me what Python is and name the source.', 'Relevant answer and official source, or an honest explanation of tool failure.'),
    ('uncertainty', 'Voice check uncertainty. What is the secret launch date of my imaginary project Blue Mango? I have not told you the date.', 'Admits the date is unknown; does not invent one.'),
    ('correction', 'Voice check correction. For this conversation, Blue Mango launches on December seventeenth, twenty twenty six. Repeat that date.', 'Repeats December 17, 2026. This is conversational input, not validated learning.'),
    ('recall', 'Voice check recall. What launch date did I just give you for Blue Mango?', 'Recalls December 17, 2026 in this conversation.'),
    ('interruption', 'Voice check interruption. Explain the water cycle slowly in detail.', 'While speaking, say: Stop. Give me just one sentence. Check speech stops and the new answer is brief.'),
)


def checklist():
    return [{'id': key, 'say': prompt, 'check': expected} for key, prompt, expected in CASES]


def evidence_report(store):
    episodes = [(item['episode'], store.read(item['episode'])) for item in store.recent()]
    results = []
    for case in checklist():
        matches = []
        for episode, events in episodes:
            transcript = ' '.join(e['payload'].get('data', {}).get('text', '')
                                  for e in events if e['kind'] == 'user_input')
            compact = re.sub(r'[^a-z0-9]', '', transcript.lower())
            if 'voicecheck' + case['id'] not in compact:
                continue
            ended = [e['payload']['data'] for e in events if e['kind'] == 'ended']
            reviews = [e['payload']['data'] for e in events if e['kind'] == 'manual_review']
            matches.append({'episode': episode,
                            'manual_review': reviews[-1] if reviews else None,
                            'timing': timing_summary(events),
                            'assistant_output_captured': any(e['kind'] == 'assistant_output' for e in events),
                            'tools': [e['payload']['data']['tool'] for e in events if e['kind'] == 'action_started'],
                            'end': ended[-1] if ended else None,
                            'capture_warning': any(e['kind'] == 'capture_health' or
                                e['payload'].get('redacted') or e['payload'].get('truncated') for e in events)})
        latest_review = matches[0]['manual_review'] if matches else None
        results.append({**case, 'matches': matches,
                        'manual_result': latest_review['result'] if latest_review else 'pending'})
    return {'scope': 'Latest 20 episodes; markers may be misheard. Capture does not verify audio or answer quality.', 'tests': results}
