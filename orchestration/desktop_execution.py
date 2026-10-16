"""Visible, isolated terminal sessions for delegated agents."""
import asyncio
import shlex
import shutil
import re

from core.secret_env import sanitized_subprocess_env
from .agent_orchestrator import AgentOrchestrator, OrchestrationError, now


CLAUDE_MODELS = {'coding': 'auto/best-coding', 'reasoning': 'auto/best-reasoning',
                 'fast': 'auto/best-fast'}


def interactive_command(agent, executable, task_type='coding'):
    if task_type not in CLAUDE_MODELS:
        raise OrchestrationError('task_type must be coding, reasoning, or fast.')
    if agent == 'codex':
        return [executable, '--no-alt-screen', '--sandbox', 'workspace-write', '--approve-for-me']
    if agent == 'claude':
        return [executable, '--model', CLAUDE_MODELS[task_type], '--permission-mode', 'auto']
    raise OrchestrationError(f'{agent} interactive desktop adapter is not implemented yet.')


class DesktopAgentOrchestrator(AgentOrchestrator):
    """Keep execution visible while monitoring only JARVIS-owned tmux panes."""

    async def _tmux(self, *args):
        process = await asyncio.create_subprocess_exec(
            'tmux', '-L', 'jarvis-desktop', *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=sanitized_subprocess_env())
        out, err = await process.communicate()
        if process.returncode:
            raise OrchestrationError(err.decode(errors='replace').strip())
        return out.decode(errors='replace')

    def discover(self):
        result = super().discover()
        result['desktop_execution'] = {
            'available': bool(shutil.which('tmux') and shutil.which('xdg-terminal-exec')),
            'surface': 'terminal',
            'application_support': 'Codex and Claude use visible terminals; other installed CLIs use the supervised process runner.'}
        for agent in result['agents']:
            agent['visible_supported'] = agent['name'] in ('codex', 'claude')
            agent['background_supported'] = agent['name'] not in ('codex', 'claude')
        return result

    def delegate(self, agent, prompt, workspace, timeout_seconds=900, task_type='coding'):
        visible = agent in ('codex', 'claude')
        if visible:
            interactive_command(agent, self.executables.get(agent), task_type)
            if isinstance(prompt, str) and any((ord(char) < 32 and char not in '\n\t') or ord(char) == 127 for char in prompt):
                raise OrchestrationError('Task text contains unsupported terminal control characters.')
            if not shutil.which('tmux') or not shutil.which('xdg-terminal-exec'):
                raise OrchestrationError('Visible delegation requires tmux and xdg-terminal-exec.')
        result = super().delegate(agent, prompt, workspace, timeout_seconds)
        job = self.jobs[result['job']['id']]
        if visible:
            job.update(surface='terminal', execution_mode='visible',
                       approval_policy='agent-native automatic review', session='jarvis-' + job['id'],
                       submission_state='waiting_for_input')
            job['task_type'] = task_type
            job['model'] = CLAUDE_MODELS[task_type] if agent == 'claude' else None
        else:
            job.update(surface='process', execution_mode='background',
                       approval_policy='agent-native command permissions',
                       submission_state='submitted')
        return self.status(job['id'])

    async def _run(self, job_id, prompt, timeout_seconds):
        job = self.jobs[job_id]
        if job['execution_mode'] == 'background':
            return await super()._run(job_id, prompt, timeout_seconds)
        session = job['session']
        launcher = None
        try:
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            command = shlex.join(interactive_command(job['agent'], self.executables[job['agent']],
                                                     job['task_type']))
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
                marker = '›' if job['agent'] == 'codex' else '❯'
                ready = (not trust_dialog and 'Enter to confirm' not in output and
                         bool(re.search(r'^\s*' + marker, output, re.MULTILINE)))
                if job['submission_state'] == 'waiting_for_input' and ready:
                    await self._tmux('send-keys', '-t', session, '-l', '\x1b[200~')
                    await self._tmux('send-keys', '-t', session, '-l', prompt)
                    await self._tmux('send-keys', '-t', session, '-l', '\x1b[201~')
                    await self._tmux('send-keys', '-t', session, 'Enter')
                    job['submission_state'] = 'submitted'
                dead = await self._tmux('display-message', '-p', '-t', session,
                                        '#{pane_dead} #{pane_dead_status}')
                if dead.startswith('1 '):
                    job['exit_code'] = int(dead.split()[1])
                    job['state'] = 'completed' if job['exit_code'] == 0 else 'failed'
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    job['state'] = 'timed_out'
                    await self._tmux('kill-session', '-t', session)
                    break
                await asyncio.sleep(.5)
            if job['cancel_requested']:
                job['state'] = 'cancelled'
                await self._tmux('kill-session', '-t', session)
        except Exception as error:
            job['state'] = 'failed'
            self._append(job, f'\nVisible launch failed: {error}\n')
            try:
                await self._tmux('kill-session', '-t', session)
            except OrchestrationError:
                pass
        finally:
            job['updated_at'] = now()
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait({key: job[key] for key in ('id', 'agent', 'state', 'workspace')})

