"""Orchestration adapters extracted from the registry facade."""
import logging
from pathlib import Path
from orchestration.agent_orchestrator import OrchestrationError
from orchestration.evolution import EvolutionManager
from core.workers import WorkerBusyError
from skills.errors import SkillError

log = logging.getLogger(__name__)


ADAPTERS = {
    'hermes.status': '_adapter_hermes_status',
    'personal_agents.create': '_adapter_create_task_agent',
    'personal_agents.status': '_adapter_task_agent_status',
    'personal_agents.list': '_adapter_list_task_agents',
    'personal_agents.cancel': '_adapter_cancel_task_agent',
    'personal_agents.followup': '_adapter_followup_task_agent',
    'harness.refine': '_adapter_start_harness_refinement',
    'learning.feedback_list': '_adapter_list_research_feedback',
    'harness.status': '_adapter_harness_status',
    'harness.start_check': '_adapter_start_harness_check',
    'harness.check_status': '_adapter_harness_check_status',
    'harness.cancel_check': '_adapter_cancel_harness_check',
    'learning.status': '_adapter_learning_status',
    'learning.lessons': '_adapter_learning_lessons',
    'learning.feedback': '_adapter_learning_feedback',
    'models.start': '_adapter_model_job',
    'models.status': '_adapter_model_job_status',
    'agents.list': '_adapter_list_system_agents',
    'agents.delegate': '_adapter_delegate_agent',
    'agents.delegate_team': '_adapter_delegate_team',
    'agents.start_goal': '_adapter_start_agent_goal',
    'agents.team_status': '_adapter_check_agent_team',
    'agents.cancel_team': '_adapter_cancel_agent_team',
    'agents.status': '_adapter_check_agent_job',
    'agents.jobs': '_adapter_list_agent_jobs',
    'agents.cancel': '_adapter_cancel_agent_job',
    'evolution.start': '_adapter_start_development',
    'evolution.request': '_adapter_request_capability',
    'evolution.status': '_adapter_development_status',
    'evolution.list': '_adapter_list_development_jobs',
    'evolution.cancel': '_adapter_cancel_development',
}

ADAPTER_COMMANDS = {
    'agents.list': (),
    'agents.delegate': (),
    'agents.status': (),
    'agents.jobs': (),
    'agents.cancel': (),
    'evolution.start': ('git', 'bwrap'),
    'evolution.request': ('git', 'bwrap'),
    'evolution.status': (),
    'evolution.list': (),
    'evolution.cancel': (),
}


class OrchestrationDomain:
    async def _adapter_list_system_agents(self):
        return self._agent_orchestrator.discover()

    async def _adapter_model_job(self, prompt, route='background'):
        from orchestration.model_routes import ModelJobs
        if not hasattr(self, '_model_jobs'):
            self._model_jobs = ModelJobs(self._memory_api_key, self.task_events)
        try:
            return self._model_jobs.start(prompt, route)
        except ValueError as error:
            raise SkillError(str(error)) from None

    async def _adapter_model_job_status(self, job_id):
        jobs = getattr(self, '_model_jobs', None)
        if jobs is None or job_id not in jobs.jobs:
            raise SkillError('Unknown model job')
        return dict(jobs.jobs[job_id])

    async def _adapter_delegate_agent(self, agent, prompt, workspace, timeout_seconds=900,
                                      task_type=None, model=None, visible=None,
                                      cost_profile='budget'):
        try:
            prompt = prompt.strip()
            options = {}
            if task_type is not None:
                options['task_type'] = task_type
            if model is None:
                from orchestration.model_policy import apply_model_policy
                routed = apply_model_policy([{'agent': agent}], cost_profile)[0]
                if routed.get('model'):
                    options['model'] = routed['model']
                if routed.get('batch'):
                    options['batch'] = True
            else:
                options['model'] = model
            if visible is not None:
                options['visible'] = visible
            return self._agent_orchestrator.delegate(agent, prompt, workspace, timeout_seconds, **options)
        except (OrchestrationError, ValueError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_delegate_team(self, goal, assignments, workspace, timeout_seconds=900):
        try:
            assignments = [
                {**assignment, 'prompt': assignment['prompt'].strip()}
                for assignment in assignments
            ]
            return self._agent_orchestrator.delegate_team(
                goal, assignments, workspace, timeout_seconds)
        except OrchestrationError as error:
            raise SkillError(str(error)) from None

    async def _adapter_start_agent_goal(self, goal, workspace, timeout_seconds=900, cost_profile='budget'):
        from orchestration.personas import software_assignments
        from orchestration.model_policy import apply_model_policy
        try:
            assignments = apply_model_policy(
                software_assignments(self._agent_orchestrator.executables), cost_profile)
        except ValueError as error:
            raise SkillError(str(error)) from None
        result = await self._adapter_delegate_team(goal, assignments, workspace, timeout_seconds)
        result['cost_policy'] = {'profile': cost_profile, 'automatic_escalation': False,
                                 'billing_limit_enforced': False}
        return result

    async def _adapter_check_agent_team(self, team_id):
        try:
            return self._agent_orchestrator.team_status(team_id)
        except OrchestrationError as error:
            raise SkillError(str(error)) from None

    async def _adapter_cancel_agent_team(self, team_id):
        try:
            return await self._agent_orchestrator.cancel_team(team_id)
        except OrchestrationError as error:
            raise SkillError(str(error)) from None

    async def _adapter_check_agent_job(self, job_id, max_chars=6000):
        try:
            return self._agent_orchestrator.status(job_id, max_chars)
        except OrchestrationError as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_agent_jobs(self):
        return self._agent_orchestrator.list_jobs()

    async def _adapter_cancel_agent_job(self, job_id):
        try:
            return await self._agent_orchestrator.cancel(job_id)
        except OrchestrationError as error:
            raise SkillError(str(error)) from None

    @property
    def evolution(self):
        if self._evolution is None:
            self._evolution = EvolutionManager(
                self._agent_orchestrator,
                can_run=lambda: self.proactive.control.get_state().can_run)
        return self._evolution

    async def _adapter_start_development(self, goal, workspace, agent='codex'):
        try:
            return await self.evolution.start(goal, workspace, agent)
        except (OrchestrationError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_request_capability(self, request, workspace, agent='codex'):
        """Turn an unsupported user request into a tracked capability proposal."""
        goal = (
            'Build the missing JARVIS capability needed for this user request. '
            'Expose it as a declared skill with strict arguments, implement it using '
            'the existing approved adapter patterns, add tests, and document how it is used. '
            'Original user request: ' + request.strip()
        )
        try:
            return await self.evolution.start(goal, workspace, agent,
                                              requested_action=request.strip())
        except (OrchestrationError, OSError, AttributeError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_development_status(self, job_id):
        try:
            manager = self._evolution or EvolutionManager(None, read_only=True)
            response = manager.status(job_id)
            job = response['job']
            # Keep voice tool context bounded; full evidence remains on disk/CLI.
            job.pop('commands', None)
            job['diff_truncated'] = job['diff_truncated'] or len(job['diff']) > 8000
            job['diff'] = job['diff'][:8000]
            for evidence in [*job['stages'], job['tests'], job['baseline_tests']]:
                if evidence:
                    output = evidence.get('output', '')
                    evidence['output_truncated'] = evidence.get('output_truncated', False) or len(output) > 3000
                    evidence['output'] = output[-3000:]
            return response
        except (OrchestrationError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_development_jobs(self):
        try:
            manager = self._evolution or EvolutionManager(None, read_only=True)
            return manager.list_jobs()
        except (OrchestrationError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_cancel_development(self, job_id):
        try:
            return await self.evolution.cancel(job_id)
        except (OrchestrationError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _learning_call(self, method, *args, **kwargs):
        if self.learning_service is None:
            if method == 'status':
                return {'enabled': False, 'automatic_refinement': False,
                        'message': 'Learning capture is disabled. Start JARVIS with --learning-dir to enable it.'}
            raise SkillError('Research learning is disabled; start with --learning-dir')
        try:
            return await self._file_worker.run(getattr(self.learning_service, method), *args, **kwargs)
        except (OSError, ValueError, KeyError, sqlite3.Error, WorkerBusyError) as error:
            raise SkillError('Research learning operation unavailable: ' + type(error).__name__) from None

    async def _adapter_learning_status(self):
        return await self._learning_call('status')

    def _personal_agents(self):
        if not hasattr(self, '_task_agents'):
            from orchestration.task_agents import TaskAgents
            root = (self.learning_service.capture.store.root if self.learning_service is not None
                    else Path(__file__).resolve().parents[2] / '.jarvis-learning')
            self._task_agents = TaskAgents(root / 'task-agents', events=self.task_events)
        return self._task_agents

    async def _adapter_hermes_status(self):
        try:
            return await self._personal_agents().capabilities()
        except (OSError, ValueError, TimeoutError) as error:
            raise SkillError('Hermes connection unavailable: ' + type(error).__name__) from None

    async def _adapter_create_task_agent(self, task, role='assistant', context='', timeout_seconds=300):
        try:
            return self._personal_agents().start(task, role=role, context=context,
                                                 timeout_seconds=timeout_seconds)
        except (OSError, ValueError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_task_agent_status(self, job_id=None):
        try:
            return self._personal_agents().status(job_id)
        except (OSError, ValueError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_task_agents(self):
        return self._personal_agents().list()

    async def _adapter_cancel_task_agent(self, job_id):
        try:
            return await self._personal_agents().cancel(job_id)
        except (OSError, ValueError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_followup_task_agent(self, job_id, message):
        try:
            return self._personal_agents().followup(job_id, message)
        except (OSError, ValueError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_research_feedback(self):
        return await self._learning_call('feedback_items')

    async def _adapter_start_harness_refinement(self, feedback_ids):
        if self.learning_service is None:
            raise SkillError('Initialize local research learning before refinement')
        try:
            # Validation reads the bounded local ledger; process launch stays on this loop.
            prepared = await self._file_worker.run(self.learning_service.prepare_refinement, feedback_ids)
            return self.learning_service.jobs.start_refinement(**prepared)
        except (OSError, ValueError, WorkerBusyError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_harness_status(self):
        if self.learning_service is None:
            from learning.jobs import local_status
            try:
                status = await self._file_worker.run(local_status)
            except (OSError, ValueError, WorkerBusyError) as error:
                raise SkillError('Local Harness status unavailable: ' + type(error).__name__) from None
            return {**status, 'learning_enabled': False,
                    'next_actions': ['Start one JARVIS instance using scripts/start-learning.sh.']}
        return await self._learning_call('harness_status')

    def _harness_jobs(self):
        if self.learning_service is None:
            raise SkillError('Local Harness checks require scripts/start-learning.sh or --learning-dir')
        return self.learning_service.jobs

    async def _adapter_start_harness_check(self):
        try:
            return self._harness_jobs().start()
        except (ValueError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_harness_check_status(self, job_id=None):
        try:
            return self._harness_jobs().status(job_id)
        except ValueError as error:
            raise SkillError(str(error)) from None

    async def _adapter_cancel_harness_check(self, job_id=None):
        try:
            return await self._harness_jobs().cancel(job_id)
        except ValueError as error:
            raise SkillError(str(error)) from None

    async def _adapter_learning_lessons(self):
        return await self._learning_call('lessons')

    async def _adapter_learning_feedback(self, text, category='other'):
        episode = self.learning_service.capture.previous if self.learning_service is not None else None
        return await self._learning_call('feedback', text, category, episode)


