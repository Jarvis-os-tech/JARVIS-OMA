"""One bounded operation using Hermes's installed authenticated gateway client.

Executed with the installed Hermes interpreter in isolated mode. Never imports
the bootstrap or starts an absent gateway. Output contains no credentials.
"""
import asyncio
import contextlib
import json
import os
from pathlib import Path
import sys
import uuid


async def operate(request):
    from hermes_cli.gateway_runtime import discover_gateway_endpoint, attachable
    from hermes_cli.gateway_client import connect_gateway
    home = Path(os.environ['HERMES_HOME'])
    # This dedicated worker has no voice/event-loop duties; discovery is bounded
    # by the installed client's local control-socket timeout.
    discovery = discover_gateway_endpoint(home)
    if not attachable(discovery):
        return {'status': 'warning', 'available': False, 'summary': 'Local Hermes gateway is not ready.',
                'next_actions': ['Start Hermes normally and retry discovery.'], 'artifacts': []}
    async with connect_gateway(endpoint=discovery.endpoint) as client:
        operation = request['operation']
        if operation == 'scheduled_results':
            from cron.executions import list_executions
            from cron.jobs import list_jobs
            names = {str(job['id']): job.get('name') or 'Scheduled task' for job in list_jobs(include_disabled=True)}
            rows = list_executions(limit=500)
            return {'events': [{'id': row['id'], 'name': names.get(str(row['job_id']), 'Scheduled task'),
                                'state': row['status'], 'finished_at': row.get('finished_at'),
                                'delivery_outcome': row.get('delivery_outcome')}
                               for row in rows if row['status'] in {'completed', 'failed', 'unknown'}]}
        if operation == 'snapshot':
            value = await client.rpc('session.resume', session_id=request['session_id'], _timeout=15)
            return {key: value.get(key) for key in ('session_id', 'execution_generation', 'running', 'prompts', 'pending', 'replay_epoch', 'last_sequence')}
        if operation == 'events':
            snapshot = await client.rpc('session.resume', session_id=request['session_id'], _timeout=15)
            epoch = request.get('replay_epoch') or snapshot.get('replay_epoch')
            replay = await client.rpc('session.events.since', session_id=request['session_id'],
                                      last_sequence=request.get('after_sequence', 0), replay_epoch=epoch, _timeout=15)
            rows = replay.pop('events', [])
            replay['events'] = [{k: (row.get('params') or row).get(k) for k in ('seq', 'sequence', 'type', 'admission_id', 'session_id')}
                                for row in rows[:200]]
            if len(rows) > 200:
                # A bounded consumer reloads the receipt on a gap; no prompt replay.
                replay.update(snapshot_required=True, truncated=True)
            return replay
        if operation == 'approval':
            return await client.rpc('approval.respond', session_id=request['session_id'],
                                    execution_generation=request['execution_generation'],
                                    prompt_id=request['prompt_id'], choice=request['choice'], _timeout=15)
        if operation == 'features':
            catalog = await client.rpc('tools.list', _timeout=15)
            commands = await client.rpc('commands.catalog', _timeout=15)
            query = request.get('query', '').casefold().strip()
            query = {'board': 'kanban', 'kanboard': 'kanban', 'cron': 'cronjob',
                     'schedules': 'cronjob', 'scheduled jobs': 'cronjob'}.get(query, query)
            rows = [row for row in catalog.get('toolsets', [])
                    if (row.get('enabled') or request.get('include_unavailable', False))
                    and (not query or query in json.dumps(row).casefold())]
            return {'status': 'success', 'available': True,
                    'summary': 'Live Hermes native features; no replacement services were created.',
                    'features': rows, 'commands': commands,
                    'availability_scope': 'Enabled by Hermes; external provider credentials and feature execution are not verified by discovery.',
                    'next_actions': [], 'artifacts': []}
        if operation == 'capabilities':
            catalog = await client.rpc('tools.list', _timeout=10)
            rows = catalog.get('toolsets', [])
            return {'status': 'success', 'available': True, 'transport': 'local_authenticated_gateway',
                    'summary': 'Existing Hermes gateway is ready; configured skills and approvals remain Hermes-owned.',
                    'toolset_count': len(rows), 'enabled_tool_count': sum(
                        row.get('tool_count', 0) for row in rows if row.get('enabled')),
                    'next_actions': [], 'artifacts': []}
        if operation == 'create':
            created = await client.rpc('session.create', cwd=request['workspace'],
                title=request.get('title') or 'Jarvis task', _timeout=15)
            return {'session_id': created['session_id']}
        session = request['session_id']
        if operation == 'admit':
            mounted = await client.rpc('session.resume', session_id=session, _timeout=15)
            if mounted.get('session_id') != session:
                raise ValueError('Session identity changed; refusing prompt')
            return await client.rpc('prompt.submit', session_id=session, text=request['prompt'],
                                    submission_id=request['submission_id'], finite=True, _timeout=15)
        if operation == 'receipt':
            receipt = await client.rpc('prompt.receipt', session_id=session,
                                       admission_id=request['admission_id'], include_result=True, _timeout=15)
            result = receipt.pop('result', None)
            if isinstance(result, dict):
                text = str(result.get('final_response') or '')
                receipt['result'] = {key: result.get(key) for key in ('completed', 'failed', 'interrupted', 'error')}
                receipt['result'].update(final_response=text[:32000], output_truncated=len(text) > 32000)
            return receipt
        if operation == 'cancel_admission':
            return await client.rpc('prompt.cancel', session_id=session,
                                    admission_id=request['admission_id'], _timeout=15)
        if operation == 'command':
            result = await client.rpc('command.dispatch', session_id=session,
                                     name=request['command'], arg=request.get('arguments', ''), _timeout=110)
            return {'status': 'success', 'native_result': result,
                    'requires_agent': result.get('type') in {'send', 'prefill', 'skill'},
                    'summary': 'Hermes returned its native command result. Interpret its directive before claiming completion.',
                    'next_actions': [], 'artifacts': []}
        if operation == 'cancel':
            try:
                # Canonical gateway resume is a read-only mount, not a prompt
                # replay. Its handle fences this interrupt against a newer turn.
                resumed = await client.rpc('session.resume', session_id=session, _timeout=15)
                if resumed.get('session_id') != session:
                    raise ValueError('Session identity changed; refusing interrupt')
                generation = resumed.get('execution_generation')
                expected = request.get('expected_generation')
                if expected is not None and generation != expected:
                    return {'acknowledged': not resumed.get('running', True), 'inactive': not resumed.get('running', True),
                            'effect': 'unknown', 'summary': 'Execution generation changed; a newer turn was not interrupted.'}
                if type(generation) is not int:
                    raise ValueError('Gateway lacks generation-fenced cancellation')
                await client.rpc('session.interrupt', session_id=session,
                                 execution_generation=generation, _timeout=10)
            except Exception as error:
                if getattr(error, 'code', None) != 4001:
                    raise
                # Disconnected turns may already be reaped. Confirm absence,
                # without sending a replacement prompt or replaying any work.
                active = await client.rpc('session.active_list', _timeout=10)
                rows = active.get('sessions')
                if not isinstance(rows, list) or any(
                        row.get('id') == session or row.get('session_id') == session
                        for row in rows):
                    raise
                return {'acknowledged': True, 'inactive': True, 'effect': 'unknown',
                        'summary': 'Owned Hermes session is no longer active; no turn was resumed.'}
            # A received RPC acknowledgement is not proof every side effect was rolled back.
            return {'acknowledged': True, 'effect': 'unknown', 'summary': 'Hermes accepted the interrupt request.'}
        if operation != 'run':
            raise ValueError('Unsupported operation')
        resumed = await client.rpc('session.resume', session_id=session, _timeout=15)
        if resumed.get('session_id') != session:
            raise ValueError('Session identity changed; refusing prompt')
        chunks, size, truncated = [], 0, False
        try:
            async with asyncio.timeout(request['timeout_seconds']):
                receipt = await client.rpc('prompt.submit', session_id=session, text=request['prompt'],
                                           submission_id=uuid.uuid4().hex, _timeout=15)
                admission = receipt.get('admission_id')
                if not admission:
                    raise ValueError('Gateway lacks turn admission correlation')
                while True:
                    frame = await client.events.get()
                    if isinstance(frame, Exception):
                        raise frame
                    params = frame.get('params') or {}
                    if params.get('session_id') != session:
                        continue
                    kind = params.get('type')
                    if kind == 'session.replay_gap':
                        raise ValueError('Session event gap; outcome unknown')
                    payload = params.get('payload') or {}
                    event_admission = params.get('admission_id') or payload.get('admission_id')
                    if event_admission != admission:
                        continue
                    if kind == 'message.delta' and isinstance(payload.get('text'), str):
                        text = payload['text']
                        remaining = 32000 - size
                        chunks.append(text[:max(0, remaining)])
                        size += len(text[:max(0, remaining)])
                        truncated |= len(text) > remaining
                    if kind == 'message.complete':
                        status = payload.get('status', 'unknown')
                        output = payload.get('final_response') or payload.get('text') or ''.join(chunks)
                        return {'status': 'completed' if status in ('completed', 'complete', 'success', 'ok') else status,
                                'output': str(output)[:32000], 'output_truncated': truncated or len(str(output)) > 32000,
                                'session_id': session, 'verified': False,
                                'summary': 'Hermes returned a result; task success requires review.'}
        except (TimeoutError, asyncio.CancelledError):
            with contextlib.suppress(Exception):
                current = await client.rpc('session.resume', session_id=session, _timeout=15)
                generation = current.get('execution_generation')
                if current.get('session_id') == session and type(generation) is int:
                    await client.rpc('session.interrupt', session_id=session,
                                     execution_generation=generation, _timeout=10)
            raise


if __name__ == '__main__':
    sys.path.insert(0, sys.argv[1])
    try:
        raw = sys.stdin.buffer.readline(65537)
        if len(raw) > 65536:
            raise ValueError('Request limit')
        request = json.loads(raw)
        result = asyncio.run(operate(request))
        print(json.dumps(result))
    except Exception as error:
        reason = str(error)
        print(json.dumps({'error': type(error).__name__, 'reason': reason if len(reason) < 100 and
                          reason.replace('_', '').isalnum() else 'request_failed', 'outcome': 'unknown'}))
        sys.exit(1)
