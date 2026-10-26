"""Bounded, local-only connection to the installed Hermes gateway.

Hermes owns its credentials, tools and approvals. This adapter never installs,
starts or updates Hermes and never adopts another client's conversations.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path
import signal
from core.secret_env import sanitized_subprocess_env


class HermesBridgeError(ValueError):
    pass


class HermesBridge:
    def __init__(self, *, home=None, source=None, python=None):
        self.home = Path(home or Path.home() / '.hermes').expanduser().resolve()
        self.source = Path(source or self.home / 'hermes-agent').resolve()
        self.python = str(python) if python else self._installed_python()
        self.owned_sessions = set()
        self._processes = set()
        self._active = set()
        self._closed = False

    def _installed_python(self):
        # Read the installed package manager receipt; importing hermes_bootstrap
        # would attempt repair/update and is deliberately avoided.
        receipts = sorted((self.home / 'installs').glob('*/facts.json'),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        for receipt in receipts:
            try:
                root = Path(json.loads(receipt.read_text())['packages']['venv']['environment'])
                python = root / 'bin' / 'python'
                if python.is_file():
                    return str(python)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return None

    async def _request(self, operation, *, timeout=20, **params):
        if self._closed:
            raise HermesBridgeError('Hermes bridge is closed')
        if not self.python or not self.source.is_dir():
            raise HermesBridgeError('Existing Hermes runtime is unavailable; no installation attempted')
        env = {key: value for key, value in sanitized_subprocess_env().items()
               if key not in {'PYTHONPATH', 'PYTHONHOME', 'HERMES_TUI_GATEWAY_URL',
                              'HERMES_HOME', 'HERMES_PROFILE'}}
        env['HERMES_HOME'] = str(self.home)
        worker = Path(__file__).with_name('_hermes_gateway_worker.py')
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(
            self.python, '-I', str(worker), str(self.source),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env, start_new_session=True))
        try:
            process = await asyncio.shield(spawn)
        except asyncio.CancelledError:
            async def stop_late_spawn():
                late = await spawn
                await self._stop(late)
            cleanup = asyncio.create_task(stop_late_spawn())
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cleanup.add_done_callback(lambda task: None if task.cancelled() else task.exception())
            raise
        self._processes.add(process)
        try:
            payload = json.dumps({'operation': operation, **params}).encode() + b'\n'
            process.stdin.write(payload)
            await process.stdin.drain()
            process.stdin.close()
            async with asyncio.timeout(timeout):
                data = bytearray()
                while chunk := await process.stdout.read(4096):
                    data.extend(chunk)
                    if len(data) > 131072:
                        raise HermesBridgeError('Hermes response exceeded the bridge output limit')
                await process.wait()
            try:
                result = json.loads(data)
            except (ValueError, UnicodeError):
                raise HermesBridgeError('Hermes transport returned no valid response; outcome may be unknown') from None
            if process.returncode or result.get('error'):
                raise HermesBridgeError('Hermes gateway request failed; inspect the owned session before retrying')
            return result
        except TimeoutError:
            raise HermesBridgeError('Hermes bridge timed out; outcome may be unknown; do not replay the task') from None
        finally:
            cleanup = asyncio.create_task(self._stop(process))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cleanup.add_done_callback(lambda task: None if task.cancelled() else task.exception())
            self._processes.discard(process)

    async def _stop(self, process):
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), 2)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                await process.wait()

    async def capabilities(self):
        try:
            return await self._request('capabilities')
        except (OSError, HermesBridgeError):
            return {'status': 'warning', 'available': False,
                    'summary': 'Existing local Hermes gateway is unavailable; no task was submitted.',
                    'next_actions': ['Check Hermes gateway status, then retry discovery.'], 'artifacts': []}

    async def create_session(self, *, workspace):
        root = Path(workspace).expanduser().resolve(strict=True)
        if not root.is_dir() or not (root / '.git').exists():
            raise HermesBridgeError('Use an isolated task Git checkout for Hermes work')
        result = await self._request('create', workspace=str(root))
        session = result.get('session_id')
        if not isinstance(session, str) or not session or len(session) > 200:
            raise HermesBridgeError('Hermes did not return a valid owned session identity')
        self.owned_sessions.add(session)
        return session

    def _owned(self, session_id):
        if session_id not in self.owned_sessions:
            raise HermesBridgeError('Only sessions created by this bridge may be used')

    async def run(self, session_id, prompt, *, timeout_seconds=300):
        self._owned(session_id)
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 20000:
            raise HermesBridgeError('Task must contain 1 to 20000 characters')
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 10 <= timeout_seconds <= 1800:
            raise HermesBridgeError('Use a timeout from 10 to 1800 seconds')
        self._active.add(session_id)
        try:
            return await self._request('run', session_id=session_id, prompt=prompt,
                                       timeout_seconds=timeout_seconds, timeout=timeout_seconds + 15)
        finally:
            self._active.discard(session_id)

    async def cancel(self, session_id):
        self._owned(session_id)
        result = await self._request('cancel', session_id=session_id)
        return {'acknowledged': result.get('acknowledged') is True, **result}

    async def close(self):
        async def stop(session_id):
            with contextlib.suppress(OSError, HermesBridgeError):
                await self.cancel(session_id)
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(12):
                await asyncio.gather(*(stop(session) for session in list(self._active)))
        self._closed = True

