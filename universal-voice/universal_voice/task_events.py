import json
from pathlib import Path
from jsonschema import Draft202012Validator
CONTRACT=json.loads(Path(__file__).with_name("task-event-v1.json").read_text())
VALIDATOR=Draft202012Validator(CONTRACT)
TERMINAL=frozenset(CONTRACT["x-terminal-states"])

def validate_event(event):
    VALIDATOR.validate(event)
    if event['terminal'] != (event['state'] in TERMINAL):
        raise ValueError('Terminal flag disagrees with task state')
    progress = event['progress']
    if progress and progress['completed'] > progress['total']:
        raise ValueError('Progress exceeds the measured total')
    evidence = event['evidence']
    if evidence['verified'] != (event['state'] == CONTRACT['x-verified-state']):
        raise ValueError('Only an evidenced completion may be marked verified')
    if evidence['verified'] and evidence['scope'] not in CONTRACT['x-verified-scopes']:
        raise ValueError('Completion needs a concrete verification scope')
    return event

