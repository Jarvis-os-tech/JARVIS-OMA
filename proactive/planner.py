"""Deterministic, bounded planning for normalized JARVIS events.

Planning is intentionally side-effect free. The returned plans can be handed to
the existing agent orchestrator by a separate caller; this module never starts
processes, calls models, or performs I/O.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping


AGENTS = ("codex", "claude", "opencode", "gemini", "hermes", "omp")
MAX_PLAN_STEPS = 8
MAX_TASK_CHARS = 4000
MAX_EVENT_ID_CHARS = 160
MAX_DEPTH = 3
MAX_SEEN_EVENTS = 512


@dataclass(frozen=True, slots=True)
class PlannedTask:
    task_id: str
    title: str
    prompt: str
    agent: str
    depth: int = 0
    depends_on: tuple[str, ...] = ()
    source_event_id: str = ""
    routing_reason: str = ""


@dataclass(frozen=True, slots=True)
class TaskPlan:
    plan_id: str
    event_id: str
    event_type: str
    status: str
    tasks: tuple[PlannedTask, ...] = ()
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "status": self.status,
            "reason": self.reason,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "prompt": task.prompt,
                    "agent": task.agent,
                    "depth": task.depth,
                    "depends_on": list(task.depends_on),
                    "source_event_id": task.source_event_id,
                    "routing_reason": task.routing_reason,
                }
                for task in self.tasks
            ],
        }


@dataclass(frozen=True, slots=True)
class _NormalizedEvent:
    event_id: str
    event_type: str
    data: Mapping[str, Any]
    depth: int
    ancestry: tuple[str, ...]


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _text(value: Any, limit: int = MAX_TASK_CHARS) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _event_mapping(event: Any) -> Mapping[str, Any]:
    if isinstance(event, Mapping):
        return event
    # Supports the project Event dataclass without coupling to its package.
    if hasattr(event, "event_type") and hasattr(event, "data"):
        return {"event_type": event.event_type, "data": event.data,
                "timestamp": getattr(event, "timestamp", None)}
    raise TypeError("event must be a mapping or an event with event_type and data")


def _normalize_event(event: Any) -> _NormalizedEvent:
    raw = _event_mapping(event)
    data_value = raw.get("data", {})
    if not isinstance(data_value, Mapping):
        data_value = {}
    event_type_value = raw.get("event_type", raw.get("type", ""))
    event_type = str(getattr(event_type_value, "value", event_type_value)).strip().casefold()
    event_type = re.sub(r"[^a-z0-9]+", "_", event_type).strip("_")
    event_id = _text(raw.get("event_id", raw.get("id", data_value.get("event_id", ""))),
                     MAX_EVENT_ID_CHARS)
    if not event_id:
        event_id = _stable_id(event_type, _text(data_value.get("text") or data_value.get("prompt")),
                              str(raw.get("timestamp", "")))
    try:
        depth_value = raw.get("depth", data_value.get("depth", 0))
        depth = int(depth_value) if not isinstance(depth_value, bool) else MAX_DEPTH + 1
    except (TypeError, ValueError, OverflowError):
        depth = MAX_DEPTH + 1
    ancestry_value = raw.get("ancestry", data_value.get("ancestry", ()))
    if isinstance(ancestry_value, str):
        ancestry = tuple(part for part in ancestry_value.split(",") if part)
    elif isinstance(ancestry_value, (list, tuple)):
        ancestry = tuple(_text(item, MAX_EVENT_ID_CHARS) for item in ancestry_value
                         if isinstance(item, str))[:MAX_SEEN_EVENTS]
    else:
        ancestry = ()
    return _NormalizedEvent(event_id, event_type, data_value, depth, ancestry)


_EVENT_ALIASES = {
    "task": "task_requested", "task_request": "task_requested", "user_request": "task_requested",
    "reminder": "reminder_due", "todo_due": "reminder_due", "agent_job_failed": "agent_failed",
    "file_change": "file_changed", "conversation_completed": "chat_exchange_completed",
}
_PLANNABLE_EVENTS = frozenset({
    "task_requested", "reminder_due", "todo_due", "agent_failed", "file_changed",
    "chat_exchange_completed", "task_updated",
})


def _select_agent(event_type: str, data: Mapping[str, Any], task_text: str) -> tuple[str, str]:
    requested = data.get("agent", data.get("preferred_agent", data.get("route")))
    if isinstance(requested, str) and requested.strip().casefold() in AGENTS:
        agent = requested.strip().casefold()
        return agent, "explicit agent selection"

    corpus = f"{event_type} {task_text}".casefold()
    # Ordered rules make overlaps predictable (e.g. browser automation involving code).
    rules = (
        ("hermes", (r"\b(computer use|desktop|screen|window|click|type into|browser ui|gui)\b",),
         "desktop interaction"),
        ("gemini", (r"\b(research|search the web|compare sources|current information|investigate)\b",),
         "research and information gathering"),
        ("claude", (r"\b(code review|review this|audit|security review|architecture review)\b",),
         "review and analysis"),
        ("omp", (r"\b(coordinate|orchestrate|multi agent|multiple agents|parallel agents)\b",),
         "explicit multi-agent coordination"),
        ("opencode", (r"\b(opencode|open code)\b",), "explicit OpenCode request"),
        ("codex", (r"\b(implement|build|fix|refactor|write code|coding|repository|repo|test suite)\b",),
         "software implementation"),
        ("gemini", (r"\b(summarize|explain|draft|brainstorm)\b",), "general knowledge task"),
    )
    for agent, patterns, reason in rules:
        if any(re.search(pattern, corpus) for pattern in patterns):
            return agent, reason
    if event_type == "agent_failed":
        return "codex", "deterministic recovery analysis default"
    return "codex", "default implementation route"


class AutonomousPlanner:
    """Turn normalized events into deterministic plans without executing them."""

    def __init__(self, *, max_steps: int = MAX_PLAN_STEPS, max_depth: int = MAX_DEPTH,
                 seen_limit: int = MAX_SEEN_EVENTS):
        for value, name, ceiling in ((max_steps, "max_steps", MAX_PLAN_STEPS),
                                      (max_depth, "max_depth", MAX_DEPTH),
                                      (seen_limit, "seen_limit", MAX_SEEN_EVENTS)):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be from 1 to {ceiling}")
        self.max_steps = max_steps
        self.max_depth = max_depth
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._seen_limit = seen_limit

    def plan(self, event: Any) -> TaskPlan:
        normalized = _normalize_event(event)
        event_type = _EVENT_ALIASES.get(normalized.event_type, normalized.event_type)
        plan_id = _stable_id(normalized.event_id, event_type)

        if normalized.event_id in normalized.ancestry:
            return TaskPlan(plan_id, normalized.event_id, event_type, "blocked", reason="event loop detected")
        if normalized.depth > self.max_depth:
            return TaskPlan(plan_id, normalized.event_id, event_type, "blocked", reason="maximum planning depth exceeded")
        if normalized.event_id in self._seen:
            return TaskPlan(plan_id, normalized.event_id, event_type, "ignored", reason="duplicate event already planned")
        self._seen[normalized.event_id] = None
        if len(self._seen) > self._seen_limit:
            self._seen.popitem(last=False)

        if event_type not in _PLANNABLE_EVENTS:
            return TaskPlan(plan_id, normalized.event_id, event_type, "ignored", reason="event type is not actionable")

        raw_tasks = normalized.data.get("tasks")
        if isinstance(raw_tasks, (list, tuple)):
            candidates = list(raw_tasks)[:self.max_steps]
        else:
            candidates = [normalized.data]
        tasks: list[PlannedTask] = []
        for index, candidate in enumerate(candidates):
            if isinstance(candidate, str):
                task_data: Mapping[str, Any] = {"prompt": candidate}
            elif isinstance(candidate, Mapping):
                task_data = candidate
            else:
                continue
            prompt = ""
            for key in ("prompt", "text", "description", "summary", "title", "content"):
                prompt = _text(task_data.get(key))
                if prompt:
                    break
            if not prompt:
                continue
            requested_agent = task_data.get("agent", task_data.get("preferred_agent", task_data.get("route")))
            if requested_agent is not None and (not isinstance(requested_agent, str) or
                                                 requested_agent.strip().casefold() not in AGENTS):
                continue
            explicit_title = _text(task_data.get("title"), 160)
            title = explicit_title or prompt[:120]
            agent, reason = _select_agent(event_type, task_data, prompt)
            task_id = _stable_id(normalized.event_id, str(index), prompt)
            tasks.append(PlannedTask(task_id, title, prompt, agent, normalized.depth,
                                     (), normalized.event_id, reason))

        if not tasks:
            return TaskPlan(plan_id, normalized.event_id, event_type, "ignored", reason="event contains no usable task")
        return TaskPlan(plan_id, normalized.event_id, event_type, "ready", tuple(tasks),
                        "bounded plan created; execution is delegated to the caller")

    def clear_seen(self) -> None:
        """Reset deduplication state, for an explicit planner lifecycle reset."""
        self._seen.clear()


def plan_event(event: Any) -> TaskPlan:
    """Convenience one-shot planner; callers needing deduplication should retain a planner."""
    return AutonomousPlanner().plan(event)


__all__ = ["AGENTS", "AutonomousPlanner", "MAX_DEPTH", "MAX_PLAN_STEPS", "MAX_TASK_CHARS",
           "PlannedTask", "TaskPlan", "plan_event"]
