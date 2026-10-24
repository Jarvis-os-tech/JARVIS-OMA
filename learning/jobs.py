"""One bounded local Harness² check, supervised outside the voice event loop."""
import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import uuid

from core.secret_env import sanitized_subprocess_env
from .bundles import BundleRegistry, private_directory
from .refinement import require_upstream, UPSTREAM_REVISION


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

    def status(self, job_id=None):
        if not self.jobs:
            if job_id:
                raise ValueError('Unknown local Harness check identity')
            return {'status': 'idle', 'kind': 'harness_refinement',
                    'summary': 'No local Harness check has been started in this JARVIS session.',
                    'next_actions': ['Ask JARVIS to run an offline Harness integration check.'], 'artifacts': {}}
        key = job_id or next(reversed(self.jobs))
        if key not in self.jobs:
            raise ValueError('Unknown local Harness check identity')
        return dict(self.jobs[key])

    def start(self):
        if self.closed:
            raise ValueError('Local Harness runner is closed; restart JARVIS')
        require_upstream()
        if self.registry.active() is None:
            raise ValueError('Initialize the local research bundle before running a check')
        if self.task is not None and not self.task.done():
            raise ValueError('A local Harness check is already running; inspect it or cancel it first')
        if len(self.jobs) >= 10:
            self.jobs.pop(next(iter(self.jobs)))
        key = 'harness-' + uuid.uuid4().hex[:12]
        self.jobs[key] = {'id': key, 'kind': 'harness_refinement', 'status': 'queued',
            'offline': True, 'activated': False, 'verified_improvement': False,
            'summary': 'Offline Harness integration check queued; no cloud model calls.',
            'next_actions': ['Continue speaking; ask for the Harness check result later.'], 'artifacts': {}}
        self.task = asyncio.create_task(self._run(key), name='jarvis-local-' + key)
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

    async def _run(self, key):
        job = self.jobs[key]
        job['status'] = 'running'
        reads = []
        try:
            work = private_directory(self.registry.root / 'checks' / key)
            environment = sanitized_subprocess_env()
            environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
            launch = asyncio.create_task(asyncio.create_subprocess_exec(
                sys.executable, '-m', 'learning', '--state-dir', str(self.registry.root),
                'refine', '--offline', '--max-calls', '32', '--seconds', '120',
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
            if (report.get('offline') is not True or report.get('activated') is not False or
                    report.get('provider') != 'offline-scripted'):
                raise ValueError('Unexpected local check report mode')
            root = Path(report['run_dir'])
            expected_parent = self.registry.root / 'refinements'
            if root.parent != expected_parent or not (root / 'report.json').is_file():
                raise ValueError('Local check returned an unexpected artifact path')
            ledger = report['ledger']
            complete = (ledger.get('R') == 4 and ledger.get('P') == 3 and
                        report.get('active_bundle_unchanged') is True and
                        set(report['assessments']) == {'base', 'inv1', 'dom1', 'c1'} and
                        set(report['holdouts']) == {'transfer', 'missing', 'conflict'} and
                        all(set(pair) == {'baseline', 'candidate'} for pair in report['holdouts'].values()) and
                        len(report['stages']) == 3 and
                        all(row.get('passed') is True for row in report['assessments'].values()) and
                        all(row.get('passed') is True for pair in report['holdouts'].values() for row in pair.values()) and
                        not any(stage.get('fell_back') or stage.get('error') for stage in report['stages']))
            job.update(status='completed' if complete else 'failed',
                summary=('Offline integration check passed. This verifies plumbing, not model improvement.' if complete else
                         'Offline integration check contains failed stages or checks; inspect its local report.'),
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

    async def cancel(self, job_id=None):
        state = self.status(job_id)
        if self.task is not None and not self.task.done() and state.get('status') in {'queued', 'running'}:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            # A task cancelled before its first tick has not entered _run.
            key = state['id']
            if self.jobs[key]['status'] == 'queued':
                self.jobs[key].update(status='cancelled', summary='Local Harness check cancelled before launch.')
        return self.status(job_id)

    async def close(self):
        self.closed = True
        await self.cancel()
