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

    def __init__(self, config: Config | None = None):
        if config is None or isinstance(config, Config):
            self.config = config or Config()
        else:
            # The voice config exposes these switches; keep the control
            # adapter's complete policy/provider defaults for other fields.
            from jarvis_voice.config import control_config
            self.config = control_config(config)
        self.executor = Executor(self.config)
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='jarvis-control')
        self._closed = False
        self._watch_events: dict[str, dict] = {}
        self._watch_sequence = 0
        schemas = tools_for(self.config)
        gemini_tools = to_gemini_tools(schemas)
        self.declarations = gemini_tools[0]["function_declarations"]
        self._tool_names = frozenset(tool["name"] for tool in self.declarations)

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """Execute a control or retrieval tool asynchronously."""
        if name not in self._tool_names:
            return f"ERROR: tool is not enabled: {name}"
        if name == "confirm_last":
            heard = str(args.get("heard_phrase", ""))
            return await self.confirm(heard)
        elif name == "cancel_last":
            return await self._run(self.cancel)
        elif name == "web_search" and args.get("background", False) and args.get("scope", "web") not in ("images", "videos"):
            from .grounding import background_google_grounding, format_grounding_result
            res = await background_google_grounding(str(args.get("query", "")))
            if res.get("ok"):
                return format_grounding_result(res)
            outcome = await self._run(self.executor.call, name, args)
            return outcome.as_tool_result()
        else:
            outcome = await self._run(self.executor.call, name, args)
            return outcome.as_tool_result()

    async def _run(self, fn, *args):
        if self._closed:
            raise RuntimeError('Control worker is closed')
        return await asyncio.get_running_loop().run_in_executor(self._worker, partial(fn, *args))

    async def close(self):
        if not self._closed:
            self._closed = True
            try:
                # Serialize camera cleanup after outstanding desktop operations.
                await asyncio.get_running_loop().run_in_executor(
                    self._worker, self.executor.vision.stop_owned)
            finally:
                await asyncio.to_thread(self._worker.shutdown, wait=True)

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
        confirm_words = getattr(
            self.config,
            "confirm_words",
            ["yes", "confirm", "proceed", "do it", "yep", "yeah", "sure"],
        )
        if not _matches(heard_phrase, confirm_words, allow_negation=False):
            phrases = ", ".join(f'"{w}"' for w in confirm_words)
            return (
                f"ERROR: '{heard_phrase}' is not a confirmation phrase, so {held} is still held. "
                f"Ask the user to say one of: {phrases}."
            )
        result = await self._run(self.executor.run_pending)
        return result.as_tool_result()

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
        agents = getattr(self.desktop, '_task_agents', None)
        if agents is None and self.desktop and hasattr(self.desktop, '_personal_agents'):
            # Discover persisted native goals after a voice restart, before any
            # new command needs to instantiate the orchestration adapter.
            agents = self.desktop._personal_agents()
        if agents is not None:
            if hasattr(agents, 'refresh'):
                await agents.refresh()
            for job in agents.jobs.values():
                if job['state'] in {'completed', 'failed', 'cancelled', 'timed_out', 'interrupted'} and not job.get('notice_acknowledged'):
                    from orchestration.task_names import task_name
                    name = job.get('name') or task_name(job.get('task'))
                    events.append({'id': 'hermes:' + job['id'],
                                   'text': f"{name}: {job['summary']}"})
        return events[:10]

    async def acknowledge_event(self, identity: str) -> None:
        if identity.startswith('hermes:'):
            agents = getattr(self.desktop, '_task_agents', None)
            if agents is not None:
                job = agents._get(identity[len('hermes:'):])
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
