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
                title='JARVIS task ' + uuid.uuid4().hex[:12], _timeout=15)
            return {'session_id': created['session_id']}
        session = request['session_id']
        if operation == 'cancel':
            answer = await client.rpc('session.interrupt', session_id=session, _timeout=10)
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
                await client.rpc('session.interrupt', session_id=session, _timeout=5)
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
