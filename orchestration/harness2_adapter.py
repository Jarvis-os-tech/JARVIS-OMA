"""Optional Harness² bridge for JARVIS delegated work.

Harness² is an optimisation framework, not a replacement for JARVIS's process
supervisor.  This bridge keeps the supervisor authoritative while exposing the
same editable harness concepts (prompt, guardrails, memory, tools, agents,
skills, scripts, plugins) to delegated runs and recording evidence for later
refinement.  It works without installing Harness² and never blocks a task on
the optimiser.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Harness2Adapter:
    """Small, failure-tolerant adapter around the optional Harness² install."""

    COMPONENTS = ("system_prompt", "guardrails", "memory", "tool_guidance",
                   "subagents", "skills", "scripts", "plugins")

    def __init__(self, root: Path | None = None, *, executable: str | None = None):
        self.root = Path(root or os.environ.get(
            "JARVIS_HARNESS2_DIR", Path.home() / ".local/state/jarvis/harness2"
        )).expanduser()
        self.executable = executable or shutil.which("harness2")

    def status(self) -> dict:
        return {
            "installed": bool(self.executable),
            "executable": self.executable,
            "state_dir": str(self.root),
            "components": list(self.COMPONENTS),
            "mode": "optional_task_refinement",
            "summary": ("Harness² adapter ready; task supervision remains owned by JARVIS."
                        if self.executable else
                        "Harness² adapter ready; install harness2 to enable recursive refinement."),
        }

    def _load_guidance(self) -> list[str]:
        path = self.root / "lessons.jsonl"
        if not path.is_file():
            return []
        out: list[str] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-20:]
        except OSError:
            return []
        # A truncated final record (for example after a power loss) must not
        # hide valid lessons written before it.  Evidence is advisory, so
        # discard only the malformed record and keep loading the rest.
        for line in lines:
            try:
                item = json.loads(line)
                lesson = item.get("lesson")
            except (ValueError, TypeError):
                continue
            if isinstance(lesson, str) and lesson.strip():
                out.append(lesson.strip()[:800])
        return out
        return out

    def prepare_prompt(self, prompt: str, *, agent: str, workspace: str) -> str:
        return (
            "Task\n"
            f"{prompt.strip()}\n\n"
            "Context\n"
            "Relevant project background.\n\n"
            "Expected result\n"
            "- Add the required functionality\n"
            "- Run the appropriate tests\n"
            "- Report changed files\n\n"
            "Constraints\n"
            "- Do not modify locked voice files\n"
            f"- Work only in the supplied workspace: {workspace}"
        )

    def record_outcome(self, *, agent: str, task: str, state: str, output: str = "") -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.root / "lessons.jsonl"
            # Store evidence only; Harness² or a later refinement job decides adoption.
            lesson = (f"{agent} task ended {state}; require explicit evidence and tests before accepting completion.")
            record = {"observed_at": _now(), "agent": agent, "state": state,
                      "lesson": lesson, "task": task[:200], "output_tail": output[-1200:]}
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            # Optimisation evidence must never make the user's task fail.
            return
