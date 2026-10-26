"""One bounded local Harness² check, supervised outside the voice event loop."""
import asyncio
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import signal
import sys
import time
import uuid
import weakref

from core.secret_env import sanitized_subprocess_env
from .bundles import BundleRegistry, private_directory
from .refinement import require_upstream, UPSTREAM_REVISION

log = logging.getLogger(__name__)
JOB_ID = re.compile(r'harness-[0-9a-f]{12}')
_SESSIONS = weakref.WeakValueDictionary()


def _process_identity(pid):
    """Linux PID-reuse-resistant identity; None means liveness is unknown."""
    try:
        fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] in {'Z', 'X'}:
            return 'exited'
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        return boot + ':' + fields[19]
    except (OSError, ValueError, IndexError):
        return None


def local_status():
    try:
        require_upstream()
    except (ImportError, OSError, ValueError) as error:
        return {'status': 'warning', 'upstream_ready': False,
                'summary': 'The existing local Harness² dependency is unavailable or differs from the reviewed version.',
                'error_type': type(error).__name__, 'next_actions': ['Inspect local dependency configuration; do not run checks yet.'],
                'artifacts': {}}
    return {'status': 'success', 'upstream_ready': True, 'revision': UPSTREAM_REVISION,
            'summary': 'The reviewed local Harness² core is available.',
            'next_actions': ['Start an offline integration check when requested.'], 'artifacts': {}}


async def read_limited(stream, limit):
    chunks = []
    size = 0
    while chunk := await stream.read(8192):
        size += len(chunk)
        if size > limit:
            raise ValueError('Local Harness check exceeded its output limit')
        chunks.append(chunk)
    return b''.join(chunks)


class LocalHarnessJobs:
    def __init__(self, root, events=None):
        self.registry = BundleRegistry(root)
        self.events = events
        self.jobs = {}
        self.task = None
        self.process = None
        self.closed = False
        self.session = uuid.uuid4().hex
        self.owner_pid = os.getpid()
        self.owner_identity = _process_identity(self.owner_pid)
        self._owned_jobs = set()
        self._lease_fd = None
        self.recovery_warnings = []
        _SESSIONS[self.session] = self
        self._recover()

    def _persist(self, key):
        """Owner-only atomic journal; a crash must not invent a completed check."""
        if not JOB_ID.fullmatch(key):
            raise ValueError('Invalid local Harness check identity')
        directory = private_directory(self.registry.root / 'checks' / key)
        journal = directory / 'job.json'
        if journal.is_symlink():
            raise ValueError('Harness journal must not be a symlink')
        data = {'version': 1, 'owner_session': self.session, 'owner_pid': self.owner_pid,
                'owner_identity': self.owner_identity, 'updated_at': time.time(),
                'job': self.jobs[key]}
        temporary = directory / ('.job-' + uuid.uuid4().hex)
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, journal)
        finally:
            temporary.unlink(missing_ok=True)

    def _recover(self):
        checks = self.registry.root / 'checks'
        if checks.is_symlink():
            self._warning('Local check directory is a symlink; history was not loaded')
            return
        if not checks.exists():
            return
        journals = []
        for directory in checks.iterdir():
            if JOB_ID.fullmatch(directory.name):
                try:
                    journals.append((directory.stat().st_mtime, directory))
                except OSError:
                    self._warning('A local check directory is unreadable')
        for _, directory in sorted(journals)[-10:]:
            try:
                if directory.is_symlink():
                    raise ValueError('Check directory is a symlink')
                descriptor = os.open(directory / 'job.json', os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, 'rb') as stream:
                    raw = stream.read(32769)
                if len(raw) > 32768:
                    raise ValueError('Journal exceeds size limit')
                record = json.loads(raw)
                job = record['job']
                if (record.get('version') != 1 or not isinstance(job, dict) or
                        job.get('id') != directory.name or job.get('kind') != 'harness_refinement' or
                        type(job.get('offline')) is not bool or job.get('activated') is not False or
                        job.get('verified_improvement') is not False or
                        job.get('status') not in {'queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted', 'unknown_needs_inspection'}):
                    raise ValueError('Invalid local check journal')
                if directory.name in self._owned_jobs:
                    continue
                self.jobs[directory.name] = job
                if job['status'] in {'queued', 'running'}:
                    owner = self._owner_state(record, directory.name)
                    if owner == 'live':
                        job.update(externally_owned=True, execution_state='owner_alive')
                    elif owner == 'unknown':
                        job.update(status='unknown_needs_inspection', execution_state='unknown', recovered=True,
                            summary='This unfinished check has no verifiable owner; inspect it before starting another check.',
                            next_actions=['Resolve the prior check owner and inspect its journal; no process was signalled.'])
                    else:
                        job.update(status='interrupted', execution_state='unknown', recovered=True,
                            summary='A previous JARVIS session ended before this check reported a result. Its child execution state is unknown.',
                            next_actions=['Inspect partial refinement artifacts; no work was resumed and no previous process was signalled.'])
                        self._persist(directory.name)
                elif job['status'] == 'completed':
                    self._validate_result_paths(job['artifacts'])
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                self.jobs.pop(directory.name, None)
                self._warning('Unreadable or invalid local check journal: ' + directory.name)

    def _warning(self, message):
        if message not in self.recovery_warnings and len(self.recovery_warnings) < 10:
            self.recovery_warnings.append(message)

    def _owner_state(self, record, key):
        pid, identity = record.get('owner_pid'), record.get('owner_identity')
        if not isinstance(pid, int) or pid <= 0 or not identity:
            return 'unknown'
        current = _process_identity(pid)
        if current is None:
            return 'dead' if not Path(f'/proc/{pid}').exists() else 'unknown'
        if current != identity:
            return 'dead'
        if pid == self.owner_pid:
            manager = _SESSIONS.get(record.get('owner_session'))
            return ('live' if manager is not None and key in manager._owned_jobs and
                    (manager.task is None or not manager.task.done()) else 'dead')
        return 'live'

    def _acquire_lease(self):
        descriptor = os.open(self.registry.root / 'local-check.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            raise ValueError('A local Harness check is already running in another JARVIS session') from None
        self._lease_fd = descriptor

    def _release_lease(self, task=None):
        self._owned_jobs.clear()
        if self._lease_fd is not None:
            os.close(self._lease_fd)
            self._lease_fd = None

    def _validate_result_paths(self, artifacts):
        root = Path(artifacts['run_dir'])
        report = Path(artifacts['report'])
        if (root.parent != self.registry.root / 'refinements' or
                not re.fullmatch('[0-9a-f]{32}', root.name) or report != root / 'report.json' or
                root.is_symlink() or report.is_symlink() or not report.is_file()):
            raise ValueError('Local check artifacts are missing or outside its state directory')
        return root

    def status(self, job_id=None):
        self._recover()
        if not self.jobs:
            if job_id:
                raise ValueError('Unknown local Harness check identity')
            return {'status': 'idle', 'kind': 'harness_refinement',
                    'summary': 'No local Harness check has been started in this JARVIS session.',
                    'next_actions': ['Ask JARVIS to run an offline Harness integration check.'], 'artifacts': {},
                    'recovery_warnings': list(self.recovery_warnings)}
        key = job_id or next(reversed(self.jobs))
        if key not in self.jobs:
            raise ValueError('Unknown local Harness check identity')
        return {**self.jobs[key], 'recovery_warnings': list(self.recovery_warnings)}

    def start(self):
        return self._start(offline=True)

    def start_refinement(self, model, feedback_ids, api_key=None):
        """Explicit cloud inference for a reviewed proposal, never automatic adoption."""
        if (not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}', model) or
                model == 'offline-scripted'):
            raise ValueError('Supply an explicit bounded cloud text model identity')
        key = api_key if api_key is not None else os.environ.get('GEMINI_API_KEY')
        if not isinstance(key, str) or not key or len(key) > 16384 or any(ord(char) < 32 for char in key):
            raise ValueError('A configured Gemini API key is required for cloud refinement')
        bundle = self.registry.active()
        if bundle is None:
            raise ValueError('Initialize the local research bundle before refinement')
        from .feedback import selected_feedback
        selected_feedback(self.registry.root, feedback_ids, bundle.digest)
        return self._start(offline=False, model=model, feedback_ids=list(feedback_ids), api_key=key)

    def _start(self, *, offline, model=None, feedback_ids=None, api_key=None):
        if self.closed:
            raise ValueError('Local Harness runner is closed; restart JARVIS')
        require_upstream()
        if self.registry.active() is None:
            raise ValueError('Initialize the local research bundle before running a check')
        if self.task is not None and not self.task.done():
            raise ValueError('A local Harness check is already running; inspect it or cancel it first')
        self._recover()
        if any(job['status'] in {'queued', 'running', 'unknown_needs_inspection'} for job in self.jobs.values()):
            raise ValueError('Another local Harness check is active or needs owner inspection; do not replay it')
        self._acquire_lease()
        if len(self.jobs) >= 10:
            self.jobs.pop(next(iter(self.jobs)))
        key = 'harness-' + uuid.uuid4().hex[:12]
        self.jobs[key] = {'id': key, 'kind': 'harness_refinement', 'status': 'queued',
            'offline': offline, 'activated': False, 'verified_improvement': False,
            **({'model': model, 'feedback_ids': feedback_ids, 'feedback_addressed_verified': False}
               if not offline else {}),
            'summary': ('Offline Harness integration check queued; no cloud model calls.' if offline else
                        'Feedback-driven Harness proposal queued using cloud inference. No automatic activation.'),
            'next_actions': ['Continue speaking; ask for the Harness check result later.'], 'artifacts': {}}
        self._owned_jobs.add(key)
        try:
            self._persist(key)
        except (OSError, ValueError):
            self.jobs.pop(key, None)
            self._release_lease()
            raise
        self.task = asyncio.create_task(self._run(key, api_key=api_key), name='jarvis-local-' + key)
        self.task.add_done_callback(self._release_lease)
        return dict(self.jobs[key])

    async def _stop_process(self):
        process = self.process
        if process is None or process.returncode is not None:
            return
        try:
            # The child owns this process group (start_new_session=True).
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), 3)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    async def _run(self, key, *, api_key=None):
        job = self.jobs[key]
        job['status'] = 'running'
        reads = []
        try:
            self._persist(key)
            work = private_directory(self.registry.root / 'checks' / key)
            environment = sanitized_subprocess_env()
            environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
            arguments = ['refine', '--max-calls', '32', '--seconds', '120']
            if job['offline']:
                arguments.append('--offline')
            else:
                # Deliberately supply this one credential only for explicit cloud work.
                # It never enters argv, journals, report summaries or model context.
                environment['GEMINI_API_KEY'] = api_key
                arguments.extend(['--model', job['model']])
                for identity in job['feedback_ids']:
                    arguments.extend(['--feedback-id', identity])
            launch = asyncio.create_task(asyncio.create_subprocess_exec(
                sys.executable, '-m', 'learning', '--state-dir', str(self.registry.root),
                *arguments,
                cwd=str(work), env=environment,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                start_new_session=True))
            try:
                self.process = await asyncio.shield(launch)
            except asyncio.CancelledError:
                # Reap a child that was created while cancellation was arriving.
                self.process = await launch
                raise
            reads = [asyncio.create_task(read_limited(self.process.stdout, 262144)),
                     asyncio.create_task(read_limited(self.process.stderr, 8192))]
            stdout, _stderr, returncode = await asyncio.wait_for(
                asyncio.gather(*reads, self.process.wait()), 150)
            if returncode:
                raise ValueError('Local Harness child did not complete successfully')
            report = json.loads(stdout)
            if (report.get('offline') is not job['offline'] or report.get('activated') is not False or
                    report.get('provider') != ('offline-scripted' if job['offline'] else job['model']) or
                    (not job['offline'] and (report.get('feedback_ids') != job['feedback_ids'] or
                                            report.get('feedback_addressed_verified') is not False))):
                raise ValueError('Unexpected local check report mode')
            root = self._validate_result_paths({'run_dir': report['run_dir'],
                                                'report': str(Path(report['run_dir']) / 'report.json')})
            with (root / 'report.json').open('rb') as stream:
                stored_report = stream.read(262145)
            if len(stored_report) > 262144 or json.loads(stored_report) != report:
                raise ValueError('Local check report differs from its persisted artifact')
            ledger = report['ledger']
            complete = (ledger.get('R') == 4 and ledger.get('P') == 3 and
                        report.get('active_bundle_unchanged') is True and
                        set(report['assessments']) == {'base', 'inv1', 'dom1', 'c1'} and
                        set(report['holdouts']) == {'transfer', 'missing', 'conflict'} and
                        all(set(pair) == {'baseline', 'candidate'} for pair in report['holdouts'].values()) and
                        len(report['stages']) == 3 and
                        {stage.get('label') for stage in report['stages']} == {'inv1', 'dom1', 'c1'} and
                        (not job['offline'] or
                         (all(row.get('passed') is True for row in report['assessments'].values()) and
                          all(row.get('passed') is True for pair in report['holdouts'].values() for row in pair.values()))) and
                        not any(stage.get('fell_back') or stage.get('error') for stage in report['stages']))
            job.update(status='completed' if complete else 'failed',
                summary=(('Offline integration check passed. This verifies plumbing, not model improvement.'
                          if job['offline'] else
                          'Feedback-driven instruction proposal completed. Review the candidate and independent checks; the reported mistake is not verified fixed.')
                         if complete else 'Harness refinement contains failed stages or checks; inspect its local report.'),
                ledger={'rollouts': ledger['R'], 'stages': ledger['P']},
                comparison=report['comparison'], model_calls=report['model_calls'],
                artifacts={'run_dir': str(root), 'report': str(root / 'report.json')},
                next_actions=['Review the local report. No candidate was activated.'])
        except asyncio.CancelledError:
            await self._stop_process()
            job.update(status='cancelled', summary='Local Harness check cancelled; partial artifacts may remain.',
                       next_actions=['Inspect partial runs before starting another check.'])
            raise
        except Exception as error:
            await self._stop_process()
            job.update(status='failed', error_type=type(error).__name__,
                summary='Local Harness check failed. No candidate was activated.',
                next_actions=['Inspect the local state directory and resolve the failure before retrying.'])
        finally:
            for reader in reads:
                if not reader.done():
                    reader.cancel()
            if reads:
                await asyncio.gather(*reads, return_exceptions=True)
            self.process = None
            if self.events is not None:
                if self.events.full():
                    job['notification_dropped'] = True
                else:
                    self.events.put_nowait(dict(job))
            try:
                self._persist(key)
            except (OSError, ValueError) as error:
                job['persistence_warning'] = type(error).__name__
                log.warning('Local Harness job state could not be persisted: %s', type(error).__name__)

    async def cancel(self, job_id=None):
        state = self.status(job_id)
        if state.get('status') in {'queued', 'running', 'unknown_needs_inspection'} and state.get('id') not in self._owned_jobs:
            raise ValueError('This check belongs to another or unknown JARVIS session; cancel it from its owning session')
        if self.task is not None and not self.task.done() and state.get('status') in {'queued', 'running'}:
            if self.task.cancelling() == 0:
                self.task.cancel()
            # A second cancel request or a cancelled voice tool must not abort
            # the supervisor while it is terminating/reaping its owned child.
            await asyncio.shield(asyncio.gather(self.task, return_exceptions=True))
            # A task cancelled before its first tick has not entered _run.
            key = state['id']
            if self.jobs[key]['status'] == 'queued':
                self.jobs[key].update(status='cancelled', summary='Local Harness check cancelled before launch.')
                self._persist(key)
        return self.status(job_id)

    async def close(self):
        self.closed = True
        if self.task is not None and not self.task.done():
            await self.cancel()
