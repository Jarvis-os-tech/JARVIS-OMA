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
import re
import fcntl
import tempfile
from core.secret_env import sanitized_subprocess_env


class HermesBridgeError(ValueError):
    pass


class HermesBridge:
    def __init__(self, *, home=None, source=None, python=None, ownership_path=None):
        self.home = Path(home or Path.home() / '.hermes').expanduser().resolve()
        self.source = Path(source or self.home / 'hermes-agent').resolve()
        self.python = str(python) if python else self._installed_python()
        self.owned_sessions = set()
        self.ownership_path = Path(ownership_path) if ownership_path else None
        if self.ownership_path and self.ownership_path.exists():
            self._load_owned()
        self._processes = set()
        self._active = set()
        self._closed = False
        self._command_session = None
        self._command_lock = asyncio.Lock()

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
                              'HERMES_HOME', 'HERMES_PROFILE', 'PRIVATE_KEY',
                              'AUTHORIZATION', 'BASH_ENV', 'ENV', 'LD_PRELOAD',
                              'LD_LIBRARY_PATH'}}
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

    async def features(self, query='', include_unavailable=False):
        if not isinstance(query, str) or len(query) > 200 or type(include_unavailable) is not bool:
            raise HermesBridgeError('Use a feature query up to 200 characters and a boolean availability flag')
        return await self._request('features', query=query, include_unavailable=include_unavailable, timeout=40)

    async def command(self, command, arguments='', *, workspace):
        if not isinstance(command, str) or not re.fullmatch(r'/?[a-zA-Z][a-zA-Z0-9_-]{0,79}', command):
            raise HermesBridgeError('Use one discovered Hermes command name, without arguments')
        if not isinstance(arguments, str) or len(arguments) > 12000 or '\x00' in arguments:
            raise HermesBridgeError('Command arguments must contain at most 12000 characters')
        async with self._command_lock:
            if self._command_session is None:
                self._command_session = await self.create_session(workspace=workspace, title='Jarvis · Hermes features')
            self._owned(self._command_session)
            return await self._request('command', session_id=self._command_session,
                                       command=command.lstrip('/'), arguments=arguments, timeout=120)

    async def create_session(self, *, workspace, title=None):
        root = Path(workspace).expanduser().resolve(strict=True)
        if not root.is_dir() or not (root / '.git').exists():
            raise HermesBridgeError('Use an isolated task Git checkout for Hermes work')
        options = {'workspace': str(root)}
        if title:
            from orchestration.task_names import task_name
            options['title'] = task_name(title)
        result = await self._request('create', **options)
        session = result.get('session_id')
        if not isinstance(session, str) or not session or len(session) > 200:
            raise HermesBridgeError('Hermes did not return a valid owned session identity')
        self.owned_sessions.add(session)
        self._persist_owned()
        return session

    def _load_owned(self):
        path = self.ownership_path
        if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
            raise HermesBridgeError('Owned-session registry must be private and locally owned')
        data = path.read_bytes()
        if len(data) > 1024 * 1024:
            raise HermesBridgeError('Owned-session registry exceeded its limit')
        rows = json.loads(data)
        if not isinstance(rows, list) or any(not isinstance(s, str) or not 1 <= len(s) <= 200 for s in rows):
            raise HermesBridgeError('Invalid owned-session registry')
        self.owned_sessions.update(rows)

    def _persist_owned(self):
        path = self.ownership_path
        if path is None:
            return
        descriptor = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            if path.exists():
                self._load_owned()
            fd, temporary = tempfile.mkstemp(prefix='.sessions-', dir=path.parent)
            try:
                with os.fdopen(fd, 'w') as stream:
                    json.dump(sorted(self.owned_sessions), stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
        finally:
            os.close(descriptor)

    async def admit(self, session_id, prompt, submission_id):
        self._owned(session_id)
        if not isinstance(submission_id, str) or not re.fullmatch('[a-zA-Z0-9_-]{1,128}', submission_id):
            raise HermesBridgeError('Invalid stable submission identity')
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 20000:
            raise HermesBridgeError('Prompt exceeds admission budget')
        return await self._request('admit', session_id=session_id, prompt=prompt,
                                   submission_id=submission_id, timeout=40)

    async def receipt(self, session_id, admission_id):
        self._owned(session_id)
        return await self._request('receipt', session_id=session_id, admission_id=admission_id)

    async def snapshot(self, session_id):
        self._owned(session_id)
        return await self._request('snapshot', session_id=session_id)

    async def respond_approval(self, session_id, prompt_id, choice, execution_generation):
        self._owned(session_id)
        snapshot = await self.snapshot(session_id)
        pending = next((p for p in snapshot.get('prompts') or [] if p.get('prompt_id') == prompt_id and p.get('kind') == 'approval'), None)
        if not pending or choice not in pending.get('choices', []) or pending.get('execution_generation') != execution_generation:
            raise HermesBridgeError('Approval is stale or its response is not allowed')
        return await self._request('approval', session_id=session_id, prompt_id=prompt_id,
                                   choice=choice, execution_generation=execution_generation)

    async def scheduled_results(self):
        return await self._request('scheduled_results')

    async def events(self, session_id, after_sequence=0, replay_epoch=None):
        self._owned(session_id)
        if type(after_sequence) is not int or after_sequence < 0:
            raise HermesBridgeError('Event cursor must be a nonnegative integer')
        return await self._request('events', session_id=session_id, after_sequence=after_sequence,
                                   replay_epoch=replay_epoch, timeout=40)

    async def cancel_admission(self, session_id, admission_id):
        self._owned(session_id)
        return await self._request('cancel_admission', session_id=session_id, admission_id=admission_id)

    def _owned(self, session_id):
        if session_id not in self.owned_sessions and self.ownership_path and self.ownership_path.exists():
            self._load_owned()
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
                                       timeout_seconds=timeout_seconds, timeout=timeout_seconds + 40)
        finally:
            self._active.discard(session_id)

    async def cancel(self, session_id, *, expected_generation=None):
        self._owned(session_id)
        options = {'expected_generation': expected_generation} if expected_generation is not None else {}
        result = await self._request('cancel', session_id=session_id, timeout=35, **options)
        return {'acknowledged': result.get('acknowledged') is True, **result}

    async def close(self):
        async def stop(session_id):
            with contextlib.suppress(OSError, HermesBridgeError):
                await self.cancel(session_id)
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(12):
                await asyncio.gather(*(stop(session) for session in list(self._active)))
        self._closed = True

