"""Control skills adapter and UnifiedSkills integration for JARVIS OS."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import logging
from typing import Any

from .config import Config
from .session import _matches
from .tools import Executor, tools_for
from . import to_gemini_tools

log = logging.getLogger(__name__)


class ControlSkills:
    """Desktop control and information retrieval skill executor."""

    def __init__(self, config: Config | None = None, call_timeout: float = 120):
        if config is None or isinstance(config, Config):
            self.config = config or Config()
        else:
            # The voice config exposes these switches; keep the control
            # adapter's complete policy/provider defaults for other fields.
            from jarvis_voice.config import control_config
            self.config = control_config(config)
        self.call_timeout = call_timeout
        self.executor = Executor(self.config)
        self._worker = ThreadPoolExecutor(max_workers=4, thread_name_prefix='jarvis-control')
        self._closed = False
        self._watch_events: dict[str, dict] = {}
        self._watch_sequence = 0
        schemas = tools_for(self.config)
        gemini_tools = to_gemini_tools(schemas)
        self.declarations = gemini_tools[0]["function_declarations"]
        self._tool_names = frozenset(tool["name"] for tool in self.declarations)

    async def execute(self, name: str, args: dict[str, Any], call_timeout: float | None = None) -> str:
        """Execute a control or retrieval tool asynchronously."""
        try:
            if name not in self._tool_names:
                return f"ERROR: tool is not enabled: {name}"
            if name == "confirm_last":
                heard = str(args.get("heard_phrase", ""))
                return await self.confirm(heard)
            elif name == "cancel_last":
                try:
                    return await self._run(self.cancel, timeout=call_timeout)
                except asyncio.TimeoutError:
                    return "ERROR: timed out"
            elif name == "web_search" and args.get("background", False) and args.get("scope", "web") not in ("images", "videos"):
                from .grounding import background_google_grounding, format_grounding_result
                res = await background_google_grounding(str(args.get("query", "")))
                if res.get("ok"):
                    return format_grounding_result(res)
                try:
                    outcome = await self._run(self.executor.call, name, args, timeout=call_timeout)
                    return outcome.as_tool_result()
                except asyncio.TimeoutError:
                    return "ERROR: timed out"
            else:
                try:
                    outcome = await self._run(self.executor.call, name, args, timeout=call_timeout)
                    return outcome.as_tool_result()
                except asyncio.TimeoutError:
                    return "ERROR: timed out"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return f"ERROR: {e}"

    def _ensure_worker(self, rebuild: bool = False):
        if getattr(self, "_worker", None) is None or rebuild:
            if getattr(self, "_worker", None) is not None:
                try:
                    self._worker.shutdown(wait=False)
                except Exception:
                    pass
            self._worker = ThreadPoolExecutor(max_workers=4, thread_name_prefix='jarvis-control')
        return self._worker

    async def _run(self, fn, *args, timeout: float | None = None):
        if self._closed:
            raise RuntimeError('Control worker is closed')
        if timeout is None:
            timeout = self.call_timeout
        self._ensure_worker()
        try:
            return await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(self._worker, partial(fn, *args)),
                timeout=timeout
            )
        except RuntimeError as e:
            if "shutdown" in str(e) or "broken" in str(e) or "cannot schedule" in str(e):
                self._ensure_worker(rebuild=True)
                return await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(self._worker, partial(fn, *args)),
                    timeout=timeout
                )
            raise

    async def close(self):
        if not self._closed:
            self._closed = True
            worker = getattr(self, "_worker", None)
            if worker is not None:
                try:
                    # Serialize camera cleanup after outstanding desktop operations.
                    await asyncio.get_running_loop().run_in_executor(
                        worker, self.executor.vision.stop_owned)
                except Exception:
                    pass
                finally:
                    await asyncio.to_thread(worker.shutdown, wait=True)

    async def background_events(self) -> list[dict]:
        """Poll off the audio loop; retain notices until delivery succeeds."""
        return await self._run(self._background_events)

    def _background_events(self) -> list[dict]:
        events = []
        if self.config.tasks_enabled:
            manager = self.executor.task_manager()
            manager.list()  # Reconcile workers which exited without a result.
            events.extend({'id': f"task:{n['id']}", 'text': n['text']}
                          for n in manager.store.notices())
        # poll_watches consumes completed watches. Keep them until acknowledged,
        # and stop consuming when delivery is unavailable and the queue is full.
        if len(self._watch_events) < 100:
            for job in self.executor.poll_watches():
                self._watch_sequence += 1
                identity = f'watch:{self._watch_sequence}'
                status = ('closed before completion could be verified' if job['vanished'] else
                          'watch timed out; completion is unknown' if job['timed_out'] else
                          'terminal became idle; inspect output for success or failure')
                self._watch_events[identity] = {
                    'id': identity,
                    'text': f"{job['label']}: {status}. {job.get('tail', '')[-1200:]}",
                }
        return (events + list(self._watch_events.values()))[:10]

    async def acknowledge_event(self, identity: str) -> None:
        await self._run(self._acknowledge_event, identity)

    def _acknowledge_event(self, identity: str) -> None:
        if identity.startswith('task:'):
            self.executor.task_manager().store.acknowledge(int(identity[5:]))
        else:
            self._watch_events.pop(identity, None)

    async def confirm(self, heard_phrase: str) -> str:
        """Confirm a held action."""
        if not self.executor.pending:
            return "ERROR: nothing is waiting for confirmation. Do not call this again."
        held = self.executor.describe(*self.executor.pending)
        confirm_words = getattr(self.config, "confirm_words", None)
        cancel_words = getattr(self.config, "cancel_words", None)
        from .nlu import NLUEngine, ConfirmationDecision
        decision = NLUEngine.evaluate_confirmation(
            heard_phrase,
            confirm_words=confirm_words,
            cancel_words=cancel_words,
            held_action=held,
        )
        if decision == ConfirmationDecision.DECLINED:
            cancel_msg = await self._run(self.cancel)
            return cancel_msg
        elif decision == ConfirmationDecision.AFFIRMED:
            result = await self._run(self.executor.run_pending)
            return result.as_tool_result()
        else:
            return (
                f"ERROR: '{heard_phrase}' did not clearly confirm or cancel {held}, so it is still held. "
                f"Ask the user conversationally if they want to proceed with {held}."
            )

    async def confirm_local(self) -> str:
        """Explicit confirmation from the private local CLI/socket."""
        result = await self._run(self.executor.run_pending)
        return result.as_tool_result()

    async def cancel_local(self) -> str:
        return await self._run(self.cancel)

    def cancel(self) -> str:
        """Cancel a held action."""
        held = self.executor.drop_pending()
        if held is None:
            return "Nothing was being held."
        return f"Cancelled: {held}"


class UnifiedSkills:
    """Combines memory skills, control skills, and desktop skills under a single interface."""

    def __init__(
        self,
        memory_skills: Any = None,
        control_skills: Any = None,
        desktop_skills: Any = None,
    ):
        self.memory = getattr(memory_skills, "memory", memory_skills)
        self._memory_skills = memory_skills
        self.control = control_skills
        self.desktop = desktop_skills
        self.config = getattr(control_skills, 'config', None) or Config()
        self._is_closed = False
        self.declarations: list[dict[str, Any]] = []

        if self._memory_skills and hasattr(self._memory_skills, "declarations"):
            self.declarations.extend(self._memory_skills.declarations)
        self._memory_names = frozenset(tool["name"] for tool in self.declarations)

        self._control_names = set()
        if self.control and hasattr(self.control, "declarations"):
            for d in self.control.declarations:
                if d["name"] not in self._memory_names:
                    self.declarations.append(d)
                    self._control_names.add(d["name"])
        self._control_names = frozenset(self._control_names)

        self._desktop_names = set()
        existing = self._memory_names | self._control_names
        if self.desktop and hasattr(self.desktop, "declarations"):
            for d in self.desktop.declarations:
                if d["name"] not in existing:
                    self.declarations.append(d)
                    self._desktop_names.add(d["name"])
        self._desktop_names = frozenset(self._desktop_names)
        # Keep the full registry for execution/IPC, but avoid sending every
        # specialist schema on every low-latency voice turn. Advanced domains
        # retain the existing discover/execute tools.
        desktop_live = getattr(self.desktop, 'live_declarations', None)
        if desktop_live is None:
            self._live_declarations = self.declarations
        else:
            live_names = {tool['name'] for tool in desktop_live}
            live_names.update({
                'call_hermes_api', 'start_hermes_goal', 'get_hermes_status',
                'linkedin_draft_post', 'linkedin_plan_sprint', 'linkedin_audit_profile',
                'linkedin_pending_reviews', 'linkedin_approve_post', 'linkedin_sync_profile',
                'linkedin_propose_tool',
            })
            self._live_declarations = [tool for tool in self.declarations
                                      if tool['name'] not in self._desktop_names or tool['name'] in live_names]
        self.on_standby_request = None
        if not any(d.get("name") == "enter_standby" for d in self.declarations):
            self.declarations.append({
                "name": "enter_standby",
                "description": "Enter private standby after confirming; 'Hey Jarvis' resumes. Use when the user says standby mode, mute, mute yourself, mute Jarvis, go to sleep, keep silent, be quiet, don't speak until recalled, or don't disturb me. A bare 'mute' means mute Jarvis via standby, never the system speaker or microphone. Do not use for an explicit request to mute system audio, mute the system microphone, pause media, or stop only the current response.",
                "parameters_json_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            })

    @property
    def live_declarations(self):
        if self._live_declarations is self.declarations:
            return self.declarations
        names = {item['name'] for item in self._live_declarations}
        return [*self._live_declarations, *[item for item in self.declarations
                if item['name'] == 'enter_standby' and item['name'] not in names]]

    @property
    def _closed(self) -> bool:
        if self._memory_skills and hasattr(self._memory_skills, "_closed"):
            return self._memory_skills._closed
        return self._is_closed

    @property
    def test_bar(self):
        if self.desktop and hasattr(self.desktop, 'test_bar'):
            return self.desktop.test_bar
        return None

    @property
    def vision_mode(self) -> str:
        if self.desktop and hasattr(self.desktop, 'vision_mode'):
            return self.desktop.vision_mode
        return getattr(self, '_vision_mode', 'off')

    @vision_mode.setter
    def vision_mode(self, mode: str):
        self._vision_mode = mode
        if self.desktop and hasattr(self.desktop, 'vision_mode'):
            self.desktop.vision_mode = mode

    async def control_vision_mode(self, mode: str, action: str = 'start') -> dict:
        if self.desktop and hasattr(self.desktop, '_adapter_control_vision_mode'):
            return await self.desktop._adapter_control_vision_mode(mode, action)
        return {'status': 'unavailable', 'vision_mode': 'off'}

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        if name == 'enter_standby':
            if getattr(self, 'on_standby_request', None) and callable(self.on_standby_request):
                res = self.on_standby_request()
                if asyncio.iscoroutine(res):
                    res = await res
                if res is None:
                    res = {
                        'status': 'standby_requested',
                        'wake_phrase': 'Hey Jarvis',
                        'message': "I am entering standby mode. Say 'Hey Jarvis' to wake me up.",
                    }
                return json.dumps(res) if isinstance(res, (dict, list)) else str(res)
            if self.desktop and hasattr(self.desktop, 'execute'):
                try:
                    res = self.desktop.execute(name, args)
                    if asyncio.iscoroutine(res):
                        res = await res
                    return json.dumps(res) if isinstance(res, (dict, list)) else str(res)
                except Exception as err:
                    return json.dumps({'error': str(err)})
            return json.dumps({'error': 'standby mode is unavailable'})
        if name in self._memory_names:
            return await self._memory_skills.execute(name, args)
        if name in self._control_names:
            return await self.control.execute(name, args)
        if name in self._desktop_names:
            res = self.desktop.execute(name, args)
            if asyncio.iscoroutine(res):
                res = await res
            if isinstance(res, (dict, list)):
                return json.dumps(res)
            return str(res)
        if self.control:
            return await self.control.execute(name, args)
        if self.desktop:
            res = self.desktop.execute(name, args)
            if asyncio.iscoroutine(res):
                res = await res
            if isinstance(res, (dict, list)):
                return json.dumps(res)
            return str(res)
        raise ValueError(f"Tool is not attached: {name}")

    def memory_context(self) -> str:
        if self._memory_skills and hasattr(self._memory_skills, "memory_context"):
            return self._memory_skills.memory_context()
        return ""

    async def background_events(self) -> list[dict]:
        events = await self.control.background_events() if self.control else []
        presented = self.desktop is not None and hasattr(self.desktop, 'refresh_task_presentation')
        if not presented:
            from orchestration.model_notices import pending_model_notices
            events.extend(pending_model_notices(self.desktop))
        agents = getattr(self.desktop, '_task_agents', None)
        if agents is None and self.desktop and hasattr(self.desktop, '_personal_agents'):
            # Discover persisted native goals after a voice restart, before any
            # new command needs to instantiate the orchestration adapter.
            agents = self.desktop._personal_agents()
        if agents is not None:
            if hasattr(agents, 'refresh'):
                await agents.refresh()
            if hasattr(agents, 'native_notices'):
                events.extend(await agents.native_notices.events())
            for job in agents.jobs.values():
                for prompt in (job.get('pending_approvals', []) if job['state'] not in {'completed','failed','cancelled','timed_out','interrupted'} else []):
                    if prompt.get('prompt_id') not in job.get('approval_notices_acknowledged', []):
                        from orchestration.task_names import task_name
                        name = job.get('name') or task_name(job.get('task'))
                        detail = prompt.get('description') or prompt.get('question') or prompt.get('command') or 'A concrete response is needed.'
                        events.append({'id': 'hermes-approval:' + job['id'] + ':' + prompt['prompt_id'],
                                       'text': f"{name}: Hermes needs your response. {detail}"})
                if not presented and job['state'] in {'completed', 'failed', 'cancelled', 'timed_out', 'interrupted'} and not job.get('notice_acknowledged'):
                    from orchestration.task_names import task_name
                    name = job.get('name') or task_name(job.get('task'))
                    suffix = ':' + str(job.get('event_sequence', 0)) if job.get('native_authority') else ''
                    events.append({'id': 'hermes:' + job['id'] + suffix,
                                   'text': f"{name}: {job['summary']}"})
        if presented:
            events.extend(await self.desktop.refresh_task_presentation())
        return events[:10]

    async def acknowledge_event(self, identity: str) -> None:
        if identity.startswith('task-event:'):
            presenter = getattr(self.desktop, '_task_presentation', None)
            if presenter is not None:
                await asyncio.to_thread(presenter.acknowledge, identity)
        elif identity.startswith('model:'):
            from orchestration.model_notices import acknowledge_model_notice
            acknowledge_model_notice(self.desktop, identity)
        elif identity.startswith('hermes-approval:'):
            agents = getattr(self.desktop, '_task_agents', None)
            if agents is not None:
                _, job_id, prompt_id = identity.split(':', 2)
                if hasattr(agents, 'transaction'):
                    with agents.transaction():
                        job = agents._get(job_id)
                        job['approval_notices_acknowledged'] = list(set(job.get('approval_notices_acknowledged', []) + [prompt_id]))
                        agents._save(job)
        elif identity.startswith('hermes-cron:'):
            agents = getattr(self.desktop, '_task_agents', None)
            if agents is not None and hasattr(agents, 'native_notices'):
                agents.native_notices.acknowledge(identity)
        elif identity.startswith('hermes:'):
            agents = getattr(self.desktop, '_task_agents', None)
            if agents is not None:
                parts = identity.split(':')
                if hasattr(agents, 'transaction'):
                    with agents.transaction():
                        job = agents._get(parts[1])
                        if len(parts) == 3 and str(job.get('event_sequence', 0)) == parts[2]:
                            job['notice_acknowledged'] = True
                            agents._save(job)
                else:
                    job = agents._get(parts[1])
                    job['notice_acknowledged'] = True
                    agents._save(job)
        elif self.control:
            await self.control.acknowledge_event(identity)

    async def context_async(self) -> str:
        if self._memory_skills and hasattr(self._memory_skills, "context_async"):
            return await self._memory_skills.context_async()
        return ""

    async def sync_companion(self, records):
        if not self._memory_skills:
            raise ValueError('Continuous memory unavailable')
        return await self._memory_skills.sync_companion(records)

    def queue_memory_exchange(self, user_text: str, assistant_text: str, device: str = "pc") -> None:
        if self._memory_skills and hasattr(self._memory_skills, "queue_memory_exchange"):
            try:
                self._memory_skills.queue_memory_exchange(user_text, assistant_text, device=device)
            except TypeError:
                self._memory_skills.queue_memory_exchange(user_text, assistant_text)

    async def start(self) -> None:
        if self._memory_skills and hasattr(self._memory_skills, "start"):
            await self._memory_skills.start()

    async def close_agent_jobs(self) -> None:
        self._is_closed = True
        try:
            if self._memory_skills and hasattr(self._memory_skills, "close_agent_jobs"):
                await self._memory_skills.close_agent_jobs()
        finally:
            try:
                if self.desktop and hasattr(self.desktop, "close_agent_jobs"):
                    await self.desktop.close_agent_jobs()
            finally:
                if self.control and hasattr(self.control, 'close'):
                    await self.control.close()
