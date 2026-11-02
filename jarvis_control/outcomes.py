"""Shared result semantics: delivery, admission and completion are distinct."""
from __future__ import annotations

from dataclasses import dataclass
import json


PENDING = frozenset({'queued', 'running', 'started', 'submitted', 'accepted',
                     'pending', 'waiting', 'validating', 'cancelling'})
FAILURES = frozenset({'error', 'failed', 'blocked', 'unavailable', 'rejected',
                      'denied', 'not_run', 'cancelled', 'interrupted', 'partial',
                      'unknown', 'needs_confirmation'})
UNVERIFIED = frozenset({'unverified', 'unverified_effect', 'dispatched',
                        'dispatched_unverified', 'requested', 'sent_unverified'})


@dataclass(frozen=True)
class Outcome:
    ok: bool
    status: str
    completed: bool
    detail: str = ''

    def response(self, result):
        response = {'ok': self.ok, 'status': self.status,
                    'completed': self.completed, 'result': result}
        if not self.ok:
            response['error'] = self.detail or self.status
        if not self.completed:
            response['guidance'] = (
                'The requested work is not confirmed complete. Inspect the result, '
                'verify its effect or check the task ID before dependent actions. '
                'Report the remaining steps or blocker; do not claim the whole request is done.'
            )
        return response


def classify_result(result, _depth=0) -> Outcome:
    """Understand legacy strings and bounded structured adapter envelopes.

    Explicit failure/uncertainty always wins over a success label. Existing
    plain-text tools retain their result contract; native input tools emit an
    explicit dispatched/unverified receipt instead of an empty success string.
    """
    if _depth > 4:
        return Outcome(False, 'unverified', False, 'Result envelope nesting is too deep')
    if isinstance(result, str):
        text = result.strip()
        if not text:
            return Outcome(False, 'unverified', False, 'No result was returned')
        if text.upper().startswith('ERROR:'):
            detail = text[6:].strip()
            held = 'needs spoken confirmation' in detail.casefold()
            return Outcome(False, 'needs_confirmation' if held else 'failed', False, detail)
        if text.startswith('[dry-run]'):
            return Outcome(True, 'dry_run', False, text)
        try:
            decoded = json.loads(text)
        except (ValueError, RecursionError):
            return Outcome(True, 'completed', True)
        if not isinstance(decoded, dict):
            return Outcome(True, 'completed', True)
        result = decoded
    if not isinstance(result, dict):
        return Outcome(False, 'unverified', False, 'Adapter returned no structured or text result')

    status = str(result.get('status', '')).casefold()
    detail = str(result.get('error') or result.get('reason') or result.get('message') or status)
    if status in FAILURES:
        return Outcome(False, 'failed' if status == 'error' else status, False, detail)
    if result.get('ok') is False or result.get('success') is False or result.get('isError') is True or result.get('error'):
        return Outcome(False, 'failed', False, detail or 'Adapter reported failure')
    if status in UNVERIFIED or result.get('verified') is False or result.get('reobserve_required') is True:
        return Outcome(False, 'unverified', False, detail or 'The effect has not been verified')
    if status in PENDING:
        return Outcome(True, status, False, detail)
    if result.get('partial') is True:
        return Outcome(False, 'partial', False, detail or 'Only part of the action completed')
    if result.get('completed') is False:
        return Outcome(False, 'incomplete', False, detail or 'Adapter explicitly reported unfinished work')
    total, completed = result.get('total_steps'), result.get('completed_steps')
    if type(total) is int and type(completed) is int and completed < total:
        return Outcome(False, 'partial', False, f'Only {completed} of {total} steps completed')
    if isinstance(result.get('steps'), list) and any(
            isinstance(step, dict) and not classify_result(step, _depth + 1).completed
            for step in result['steps']):
        return Outcome(False, 'partial', False, 'One or more requested steps are unfinished')
    for key in ('task', 'job', 'goal', 'result', 'output'):
        child = result.get(key)
        if isinstance(child, (dict, str)) and child:
            nested = classify_result(child, _depth + 1)
            if not nested.completed:
                return nested
    if status == 'dry_run':
        return Outcome(True, 'dry_run', False, detail)
    return Outcome(True, 'completed', True)
