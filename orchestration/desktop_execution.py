"""Visible, isolated terminal sessions for delegated agents."""
import asyncio
import os
import re
import shlex
import shutil
import stat
import json
from pathlib import Path
import tempfile

from core.secret_env import sanitized_subprocess_env
from .agent_orchestrator import AgentOrchestrator, OrchestrationError, now, validate_model, command_for


CLAUDE_MODELS = {
    'coding': 'auto/best-coding',
    'reasoning': 'auto/best-reasoning',
    'fast': 'auto/best-fast',
}

PROMPT_MARKERS = {
    'codex': r'[›>]',
    'claude': r'[❯>]',
    'opencode': r'(?:[❯›>]|┃\s*Ask anything)',
    'gemini': r'[❯›>]',
    'hermes': r'[❯›>]',
    'omp': r'[❯›>]',
    'pi': r'[❯›>]',
    'crush': r'[❯›>]',
}


def visible_batch_command(agent, executable, prompt, model=None, yolo=False):
    """Finite agent turns shown in tmux, preserving configured model/provider."""
    command = command_for(agent, executable, prompt, model=model)
    if yolo:
        if agent == 'claude':
            index = command.index('--permission-mode')
            del command[index:index + 2]
            command.insert(1, '--dangerously-skip-permissions')
        elif agent == 'hermes':
            command.insert(1, '--yolo')
        elif agent == 'opencode':
            command.insert(2, '--auto')
        else:
            raise OrchestrationError(f'YOLO batch execution is not configured for {agent}')
    return command


def native_task_command(agent, executable, prompt, model=None, yolo=False):
    """Start the real interactive frontend with its first task populated."""
    validate_model(model)
    if agent == 'claude':
        command = [executable]
        if yolo:
            command.append('--dangerously-skip-permissions')
        if model:
            command.extend(['--model', model])
        return command + [prompt]
    if agent == 'hermes':
        command = [executable, 'chat', '--tui']
        if yolo:
            command.append('--yolo')
        if model:
            command.extend(['--model', model])
        return command + ['--query', prompt]
    if agent == 'opencode':
        if model:
            raise OrchestrationError('Native OpenCode uses its configured model; per-task overrides require batch mode.')
        return [executable, *(['--auto'] if yolo else []), '--prompt', prompt]
    raise OrchestrationError(f'Native task frontend is not configured for {agent}')


def interactive_command(agent, executable, task_type='coding', model=None):
    validate_model(model)
    if task_type is not None and task_type not in CLAUDE_MODELS:
        raise OrchestrationError('task_type must be coding, reasoning, or fast.')

    selected_claude_model = model or (CLAUDE_MODELS.get(task_type) if task_type else CLAUDE_MODELS['coding'])

    if agent == 'codex':
        cmd = [executable, '--no-alt-screen', '--sandbox', 'workspace-write', '--approve-for-me']
        if model:
            cmd.extend(['--model', model])
        return cmd
    if agent == 'claude':
        cmd = [executable]
        if selected_claude_model:
            cmd.extend(['--model', selected_claude_model])
        cmd.extend(['--permission-mode', 'auto'])
        return cmd
    if agent == 'opencode':
        cmd = [executable, '--auto']
        if model:
            cmd.extend(['--model', model])
        return cmd
    if agent == 'gemini':
        cmd = [executable, '--approval-mode', 'auto_edit', '--skip-trust']
        if model:
            cmd.extend(['-m', model])
        return cmd
    if agent == 'hermes':
        cmd = [executable, 'chat']
        if model:
            cmd.extend(['-m', model])
        return cmd
    if agent == 'omp':
        cmd = [executable, '--approval-mode', 'write']
        if model:
            cmd.extend(['--model', model])
        return cmd
    if agent == 'pi':
        cmd = [executable]
        if model:
            cmd.extend(['--model', model])
        return cmd
    if agent == 'crush':
        cmd = [executable]
        if model:
            cmd.extend(['--model', model])
        return cmd
    raise OrchestrationError(f'{agent} interactive desktop adapter is not implemented yet.')


class DesktopAgentOrchestrator(AgentOrchestrator):
    """Keep execution visible while monitoring only JARVIS-owned tmux panes."""

    _COMPLETION_REPORT_LIMIT = 4096

    def _completion_path(self, job):
        parent = Path(tempfile.mkdtemp(prefix='jarvis-completion-'))
        flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        directory_fd = os.open(parent, flags)
        identity = os.fstat(directory_fd)
        completion = parent / 'result.json'
        job['completion_file'] = str(completion)
        job['completion_directory_fd'] = directory_fd
        job['completion_directory_identity'] = (identity.st_dev, identity.st_ino)
        return completion

    @staticmethod
    def _completion_task(prompt, completion):
        return (prompt + '\n\nJARVIS handoff protocol: when your assignment is finished, '
                'write a JSON object to ' + str(completion) + ' with state "completed" '
                'and a brief summary. If blocked, write state "failed" and explain why. '
                'Write this file as your final tool action, then give your normal final response. '
                'This is a task-completion report, not independent proof of correctness.')

    def _read_completion_report(self, completion, job=None):
        descriptor = None
        try:
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
            directory_fd = job.get('completion_directory_fd') if job else None
            if directory_fd is not None:
                descriptor = os.open(completion.name, flags, dir_fd=directory_fd)
            else:
                descriptor = os.open(completion, flags)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > self._COMPLETION_REPORT_LIMIT:
                return None
            payload = os.read(descriptor, self._COMPLETION_REPORT_LIMIT + 1)
            if len(payload) > self._COMPLETION_REPORT_LIMIT:
                return None
            report = json.loads(payload.decode('utf-8'))
        except (OSError, UnicodeError, ValueError):
            return None
        finally:
            if descriptor is not None:
                os.close(descriptor)
        if not isinstance(report, dict) or report.get('state') not in ('completed', 'failed'):
            return None
        summary = report.get('summary')
        if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 2000:
            return None
        if any((ord(char) < 32 and char not in '\n\t') or ord(char) == 127
               for char in summary):
            return None
        return {'state': report['state'], 'summary': summary.strip()}

    def _accept_completion_report(self, job, completion):
        report = self._read_completion_report(completion, job)
        if report is None:
            return False
        job['reported_state'] = report['state']
        job['state'] = 'verifying' if report['state'] == 'completed' else 'failed'
        job['completion_report'] = report
        job['completion_source'] = 'agent report; process retirement pending'
        job['terminal_state'] = 'open'
        self._append(job, '\nAgent handoff report: ' + json.dumps(report) + '\n')
        return True

    async def _retire_completed_process(self, job, target):
        """Stop a reported-complete TUI while retaining an inspectable dead pane."""
        reported_state = job.get('reported_state', job['state'])
        try:
            await self._tmux(
                'respawn-pane', '-k', '-t', target,
                'printf "\\nJARVIS task finished; captured output is available in job history.\\n"',
            )
        except OrchestrationError as error:
            job['reported_state'] = reported_state
            job['state'] = 'cleanup_failed'
            job['terminal_state'] = 'open'
            job['completion_source'] = 'agent report; process retirement could not be confirmed'
            self._append(job, f'\nAgent process cleanup could not be confirmed: {error}\n')
            return False
        job['terminal_state'] = 'closed'
        job['completion_source'] = (
            'agent report; terminal process retired for safe workspace release')
        return True

    @staticmethod
    def _cleanup_completion_path(completion, job=None):
        if completion is None:
            return
        directory_fd = job.pop('completion_directory_fd', None) if job else None
        expected = job.pop('completion_directory_identity', None) if job else None
        try:
            if directory_fd is not None:
                try:
                    os.unlink(completion.name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                current = os.lstat(completion.parent)
                opened = os.fstat(directory_fd)
                if (not stat.S_ISLNK(current.st_mode)
                        and (current.st_dev, current.st_ino) == expected
                        and (opened.st_dev, opened.st_ino) == expected):
                    completion.parent.rmdir()
            else:
                completion.unlink(missing_ok=True)
                completion.parent.rmdir()
        except OSError:
            pass
        finally:
            if directory_fd is not None:
                os.close(directory_fd)

    async def _cleanup_tmux(self, kind, target):
        """Best-effort cleanup for a pane/session owned by this orchestrator."""
        try:
            await self._tmux('kill-' + kind, '-t', target)
            return True
        except OrchestrationError:
            return False

    def _emit_team_event(self, team_id):
        team = self.teams[team_id]
        if self.events.full():
            self.events.get_nowait()
        self.events.put_nowait({
            'kind': 'team', 'id': team_id,
            'state': 'response_received' if team['state'] == 'completed' and not team.get('verified') else team['state'],
            'verified': team.get('verified', False), 'completion_kind': team.get('completion_kind'),
            'workspace': team['workspace'],
        })

    async def _tmux(self, *args):
        process = await asyncio.create_subprocess_exec(
            'tmux', '-L', 'jarvis-desktop', *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=sanitized_subprocess_env())
        try:
            out, err = await process.communicate()
        except asyncio.CancelledError:
            # Let an in-flight tmux mutation finish before session cleanup;
            # otherwise new-session can complete after kill-session runs.
            await process.communicate()
            raise
        if process.returncode:
            raise OrchestrationError(err.decode(errors='replace').strip())
        return out.decode(errors='replace')

    def discover(self):
        result = super().discover()
        terminal_available = bool(shutil.which('tmux') and shutil.which('xdg-terminal-exec'))
        result['desktop_execution'] = {
            'available': terminal_available,
            'surface': 'terminal',
            'application_support': (
                'All supported agents can launch in visible tmux terminals when terminal tools are available, '
                'or run via the supervised background runner.'
            ),
        }
        for agent in result['agents']:
            agent['visible_supported'] = terminal_available and agent['available']
            agent['background_supported'] = agent['available']
        return result

    def _preflight_team(self, assignments):
        """Build every planned command before creating a team or terminal."""
        shared_terminal = all(assignment['visible'] for assignment in assignments)
        for assignment in assignments:
            agent = assignment['agent']
            executable = self.executables.get(agent)
            model = assignment.get('model')
            if shared_terminal:
                builder = visible_batch_command if assignment.get('batch') else native_task_command
                builder(agent, executable, assignment['prompt'], model=model,
                        yolo=assignment.get('yolo', False))
            elif assignment['visible']:
                if assignment.get('batch'):
                    visible_batch_command(agent, executable, assignment['prompt'], model=model,
                                          yolo=assignment.get('yolo', False))
                interactive_command(agent, executable,
                                    task_type=assignment.get('task_type', 'coding'), model=model)
            else:
                command_for(agent, executable, assignment['prompt'], model=model)

    def delegate(self, agent, prompt, workspace, timeout_seconds=900, task_type='coding', model=None, visible=True, batch=False, yolo=True):
        if batch:
            visible_batch_command(agent, self.executables.get(agent), prompt, model, yolo)
        if visible:
            interactive_command(agent, self.executables.get(agent), task_type=task_type, model=model)
            if isinstance(prompt, str) and any((ord(char) < 32 and char not in '\n\t') or ord(char) == 127 for char in prompt):
                raise OrchestrationError('Task text contains unsupported terminal control characters.')
            if not shutil.which('tmux') or not shutil.which('xdg-terminal-exec'):
                raise OrchestrationError('Visible delegation requires tmux and xdg-terminal-exec.')
        result = super().delegate(agent, prompt, workspace, timeout_seconds, model=model)
        job = self.jobs[result['job']['id']]
        if visible:
            job.update(surface='terminal', execution_mode='visible',
                       approval_policy='agent-native automatic review', session='jarvis-' + job['id'],
                       submission_state='waiting_for_input')
            job['task_type'] = task_type
            job['model'] = model or (CLAUDE_MODELS.get(task_type) if agent == 'claude' else None)
            if batch:
                job.update(batch=True, yolo=yolo, model=model,
                           submission_state='submitted',
                           approval_policy='YOLO requested by user' if yolo else 'agent-native command permissions')
        else:
            job.update(surface='process', execution_mode='background',
                       approval_policy='agent-native command permissions',
                       submission_state='submitted')
            job['task_type'] = task_type
            job['model'] = model
        return self.status(job['id'])

    def _delegate_team_assignment(self, assignment, prompt, workspace, timeout_seconds):
        result = self.delegate(
            assignment['agent'], prompt, workspace, timeout_seconds,
            task_type=assignment['task_type'], model=assignment['model'],
            visible=assignment['visible'], batch=assignment.get('batch', False),
            yolo=assignment.get('yolo', True))
        if assignment.get('_pane'):
            self.jobs[result['job']['id']].update(
                shared_pane=assignment['_pane'], model=assignment.get('model'),
                batch=assignment.get('batch', False), yolo=assignment.get('yolo', True))
        return result

    async def _run_team(self, team_id, timeout_seconds):
        team = self.teams[team_id]
        if team['cancel_requested'] or self._stopped or not all(a.get('visible') for a in team['assignments']):
            return await super()._run_team(team_id, timeout_seconds)
        session = 'jarvis-' + team_id
        team['tmux_session'] = session
        session_created = False
        session_setup_started = False
        delegated = False
        try:
            placeholder = shlex.join(['tmux', '-L', 'jarvis-desktop', 'wait-for', session + '-idle'])
            session_setup_started = True
            first = (await self._tmux('new-session', '-d', '-P', '-F', '#{pane_id}',
                '-s', session, '-c', team['workspace'], '-x', '180', '-y', '50', placeholder)).strip()
            session_created = True
            panes = [first]
            await self._tmux('set-option', '-t', session, 'remain-on-exit', 'on')
            await self._tmux('set-option', '-t', session, 'pane-border-status', 'top')
            await self._tmux('set-option', '-t', session, 'pane-border-format', '#{@jarvis_role}')
            for _ in team['assignments'][1:]:
                panes.append((await self._tmux('split-window', '-d', '-P', '-F', '#{pane_id}',
                    '-t', session, '-c', team['workspace'], placeholder)).strip())
                await self._tmux('select-layout', '-t', session, 'tiled')
            for index, (assignment, pane) in enumerate(zip(team['assignments'], panes)):
                assignment['_pane'] = pane
                await self._tmux('select-pane', '-t', pane, '-T', f'{index + 1}: {assignment["agent"]}')
                await self._tmux('set-option', '-p', '-t', pane, '@jarvis_role',
                                 f'{index + 1}: {assignment["agent"]}')
            await self._tmux('select-pane', '-t', panes[0])
            team['tmux_session'] = session
            await asyncio.create_subprocess_exec(
                'xdg-terminal-exec', 'tmux', '-L', 'jarvis-desktop', 'attach-session', '-t', session,
                cwd=team['workspace'], start_new_session=True, env=sanitized_subprocess_env())
            delegated = True
            await super()._run_team(team_id, timeout_seconds)
        except asyncio.CancelledError:
            if session_setup_started:
                team['state'] = 'cleaning_up'
                if await self._cleanup_tmux('session', session):
                    session_created = False
            if session_created:
                team.update(state='cleanup_failed', failure_state='cancelled')
            else:
                team['state'] = 'cancelled'
            team.update(current_assignment=None, updated_at=now())
            raise
        except Exception as error:
            if session_setup_started:
                team['state'] = 'cleaning_up'
                if await self._cleanup_tmux('session', session):
                    session_created = False
            if session_created:
                team.update(state='cleanup_failed', failure_state='failed')
            else:
                team['state'] = 'failed'
            team.update(error=str(error)[:500], updated_at=now())
        finally:
            if session_created and team['state'] in ('failed', 'cancelled', 'timed_out', 'cleanup_failed'):
                if await self._cleanup_tmux('session', session):
                    session_created = False
                    if team['state'] == 'cleanup_failed':
                        team['state'] = team.pop('failure_state')
                else:
                    team.setdefault('failure_state', team['state'])
                    team['state'] = 'cleanup_failed'
            if not delegated:
                self._emit_team_event(team_id)

    async def _run(self, job_id, prompt, timeout_seconds):
        job = self.jobs[job_id]
        if job['execution_mode'] == 'background':
            return await super()._run(job_id, prompt, timeout_seconds)
        # Visible terminals have their own execution loop, so prepare the
        # prompt here before either batch or interactive submission.
        prompt = self._prepare_prompt(job, prompt)
        session = job['session']
        if job.get('shared_pane'):
            return await self._run_shared_pane(job_id, prompt, timeout_seconds, prepared=True)
        launcher = None
        completion = None
        try:
            from proactive.verification import capture_workspace
            baseline = await capture_workspace(job['workspace'])
            if job['cancel_requested']:
                job['state'] = 'cancelled'
                return
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            if job.get('batch'):
                command = shlex.join(visible_batch_command(
                    job['agent'], self.executables[job['agent']], prompt,
                    model=job.get('model'), yolo=job.get('yolo', False)))
            else:
                completion = self._completion_path(job)
                prompt = self._completion_task(prompt, completion)
                command = shlex.join(interactive_command(job['agent'], self.executables[job['agent']],
                                                         task_type=job.get('task_type', 'coding'),
                                                         model=job.get('model')))
            # Start with an idle pane so the agent detects the attached terminal,
            # rather than the environment of the voice service.
            placeholder = shlex.join(['tmux', '-L', 'jarvis-desktop', 'wait-for', session + '-launch'])
            await self._tmux('new-session', '-d', '-s', session, '-c', job['workspace'],
                             '-x', '120', '-y', '40', placeholder)
            await self._tmux('set-option', '-t', session, 'status', 'off')
            await self._tmux('set-option', '-t', session, 'default-terminal', 'tmux-256color')
            await self._tmux('set-option', '-t', session, 'terminal-overrides', ',*:RGB')
            await self._tmux('set-option', '-t', session, 'remain-on-exit', 'on')
            launcher = await asyncio.create_subprocess_exec(
                'xdg-terminal-exec', 'tmux', '-L', 'jarvis-desktop', 'attach-session', '-t', session,
                cwd=job['workspace'], start_new_session=True,
                env=sanitized_subprocess_env())
            while (await self._tmux('display-message', '-p', '-t', session,
                                   '#{session_attached}')).strip() in ('', '0'):
                if job['cancel_requested']:
                    job['state'] = 'cancelled'
                    await self._tmux('kill-session', '-t', session)
                    return
                if launcher.returncode not in (None, 0):
                    raise OrchestrationError('Terminal application failed to launch.')
                if asyncio.get_running_loop().time() >= deadline:
                    job['state'] = 'timed_out'
                    await self._tmux('kill-session', '-t', session)
                    return
                await asyncio.sleep(.1)
            await self._tmux('respawn-pane', '-k', '-t', session, '-c', job['workspace'],
                             'exec env TERM=tmux-256color COLORTERM=truecolor ' + command)
            job['state'] = 'running'
            job['terminal_state'] = 'open'
            while not job['cancel_requested']:
                if launcher.returncode not in (None, 0):
                    raise OrchestrationError('Terminal application failed to launch.')
                output = await self._tmux('capture-pane', '-p', '-t', session, '-S', '-2000')
                job['output'] = ''
                self._append(job, output)
                if 'auto mode unavailable for this model' in output:
                    job['approval_policy'] = 'manual: automatic review unavailable for selected model'
                trust_dialog = (job['agent'] == 'claude' and
                                'Accessing workspace:' in output and
                                'Yes, I trust this folder' in output and
                                'Enter to confirm' in output)
                if trust_dialog and not job.get('workspace_trust_confirmed'):
                    if '❯ No, exit' not in output:
                        raise OrchestrationError('Unrecognized workspace trust selection.')
                    await self._tmux('send-keys', '-t', session, 'Down', 'Enter')
                    job['workspace_trust_confirmed'] = True
                    await asyncio.sleep(.5)
                    continue
                # Submit only after the interactive agent's composer appears.
                # No arbitrary approval-dialog keystrokes are inferred from output.
                marker_pattern = PROMPT_MARKERS.get(job['agent'], r'[›❯>]')
                ready = (not trust_dialog and 'Enter to confirm' not in output and
                         bool(re.search(r'^\s*' + marker_pattern, output, re.MULTILINE)))
                if job['submission_state'] == 'waiting_for_input' and ready:
                    await self._tmux('send-keys', '-t', session, '-l', '\x1b[200~')
                    await self._tmux('send-keys', '-t', session, '-l', prompt)
                    await self._tmux('send-keys', '-t', session, '-l', '\x1b[201~')
                    await self._tmux('send-keys', '-t', session, 'Enter')
                    job['submission_state'] = 'submitted'
                if completion is not None and self._accept_completion_report(job, completion):
                    await self._retire_completed_process(job, session)
                    break
                dead = await self._tmux('display-message', '-p', '-t', session,
                                        '#{pane_dead} #{pane_dead_status}')
                if dead.startswith('1 '):
                    job['exit_code'] = int(dead.split()[1])
                    job['state'] = 'verifying' if job['exit_code'] == 0 else 'failed'
                    job['terminal_state'] = 'closed'
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    job['state'] = 'timed_out'
                    await self._tmux('kill-session', '-t', session)
                    job['terminal_state'] = 'closed'
                    break
                await asyncio.sleep(.5)
            if job['cancel_requested']:
                job['state'] = 'cancelled'
                await self._tmux('kill-session', '-t', session)
                job['terminal_state'] = 'closed'
            await self._verify_completion(job, baseline)
        except asyncio.CancelledError:
            job['state'] = 'cancelled'
            await self._cleanup_tmux('session', session)
            raise
        except Exception as error:
            job['state'] = 'failed'
            self._append(job, f'\nVisible launch failed: {error}\n')
            try:
                await self._tmux('kill-session', '-t', session)
                job['terminal_state'] = 'closed'
            except OrchestrationError:
                pass
        finally:
            self._cleanup_completion_path(completion, job)
            job['updated_at'] = now()
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait(self._completion_event(job))

    async def _run_shared_pane(self, job_id, prompt, timeout_seconds, prepared=False):
        job = self.jobs[job_id]
        if not prepared:
            prompt = self._prepare_prompt(job, prompt)
        pane = job['shared_pane']
        completion = None
        seed_task = None
        pane_alive = False
        try:
            from proactive.verification import capture_workspace
            baseline = await capture_workspace(job['workspace'])
            if job['cancel_requested']:
                job['state'] = 'cancelled'
                return
            if job.get('batch'):
                command = visible_batch_command(job['agent'], self.executables[job['agent']],
                    prompt, model=job.get('model'), yolo=job.get('yolo', False))
            else:
                completion = self._completion_path(job)
                task = self._completion_task(prompt, completion)
                command = native_task_command(job['agent'], self.executables[job['agent']],
                    task, model=job.get('model'), yolo=job.get('yolo', False))
                if job['agent'] == 'hermes':
                    # Installed Hermes TUI ignores --query; submit after its
                    # actual composer appears instead of assuming startup worked.
                    command = command[:-2]
                    seed_task = task
            await self._tmux('respawn-pane', '-k', '-t', pane, '-c', job['workspace'],
                'exec env TERM=tmux-256color COLORTERM=truecolor ' + shlex.join(command))
            pane_alive = True
            await self._tmux('select-pane', '-Z', '-t', pane)
            if (await self._tmux('display-message', '-p', '-t', pane, '#{window_zoomed_flag}')).strip() == '0':
                await self._tmux('resize-pane', '-Z', '-t', pane)
            job['state'] = 'running'
            job['terminal_state'] = 'open'
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            while True:
                output = await self._tmux('capture-pane', '-p', '-t', pane, '-S', '-2000')
                job['output'] = ''
                self._append(job, output)
                if seed_task is not None and re.search(r'^\s*❯', output, re.MULTILINE):
                    await self._tmux('send-keys', '-t', pane, '-l', '\x1b[200~' + seed_task + '\x1b[201~')
                    await self._tmux('send-keys', '-t', pane, 'Enter')
                    seed_task = None
                if completion is not None and self._accept_completion_report(job, completion):
                    pane_alive = not await self._retire_completed_process(job, pane)
                    break
                dead = (await self._tmux('display-message', '-p', '-t', pane,
                                        '#{pane_dead} #{pane_dead_status}')).strip()
                if dead.startswith('1 '):
                    pane_alive = False
                    job['terminal_state'] = 'closed'
                    job['exit_code'] = int(dead.split()[1])
                    job['state'] = 'verifying' if completion is None and job['exit_code'] == 0 else 'failed'
                    break
                if job['cancel_requested'] or asyncio.get_running_loop().time() >= deadline:
                    job['state'] = 'cancelled' if job['cancel_requested'] else 'timed_out'
                    await self._tmux('kill-pane', '-t', pane)
                    pane_alive = False
                    job['terminal_state'] = 'closed'
                    break
                await asyncio.sleep(.5)
            await self._verify_completion(job, baseline)
        except asyncio.CancelledError:
            if pane_alive:
                await self._cleanup_tmux('pane', pane)
            job['state'] = 'cancelled'
            raise
        except Exception as error:
            self._append(job, f'\nPane execution failed: {error}\n')
            if pane_alive:
                cleaned = await self._cleanup_tmux('pane', pane)
                if not cleaned:
                    self._append(job, '\nPane cleanup could not be confirmed; workspace remains reserved.\n')
                    job['state'] = 'cleanup_failed'
                else:
                    pane_alive = False
                    job['state'] = 'failed'
            else:
                job['state'] = 'failed'
        finally:
            self._cleanup_completion_path(completion, job)
            job['updated_at'] = now()
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait(self._completion_event(job))
