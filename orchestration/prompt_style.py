"""Canonical Omarchy / JARVIS Prompt Style Engine.

Enforces radical epistemic honesty, non-destructive system boundaries,
zero-polling hardware physics, purposeful motion budgets, and strict test-backed
verification across all delegated agent tasks and model prompts.
"""
from __future__ import annotations

ROLE_GUIDELINES = {
    'coding': (
        "- Implement the goal using verified repository patterns and minimal blast radius.\n"
        "- Non-destructive default: /usr/share/omarchy is immutable; user edits belong in ~/.config with backups.\n"
        "- Zero-polling rule: never use periodic timers for state; use DBus signals, IPC pipes, or FileView.\n"
        "- Purposeful motion: transitions <300ms, asymmetric 2/3 exits, tokenize with Style.duration(ms).\n"
        "- Preserve unrelated files and code style; do not reformat untouched code."
    ),
    'qa': (
        "- Independently verify and test the implementation against acceptance criteria.\n"
        "- Work strictly from evidence: run actual tests or headless checks; never assume pass.\n"
        "- Report exact reproduction steps, stack traces, and remaining defects without speculation."
    ),
    'research': (
        "- Inspect the codebase, system state, and documentation to build an evidence-backed plan.\n"
        "- Distinguish proven facts from plausible inferences.\n"
        "- Do not modify application source code during research."
    ),
    'triage': (
        "- Establish facts from coredumpctl info <pid> and system journal logs.\n"
        "- Rule out resource exhaustion (free -h, OOM killer) before blaming code defects.\n"
        "- Structure findings into the 4-point report: What crashed, Likely mechanism, Data loss/recovery, Recurrence/fix.\n"
        "- Clean up ephemeral core dumps in mktemp immediately."
    ),
    'customization': (
        "- Apply the Overlay Pattern: write deltas strictly to ~/.config/, never /usr/share/omarchy/.\n"
        "- 5-step mutation cycle: Read -> Backup (file.bak.$(date +%s)) -> Write -> Validate -> Rollback on error."
    ),
}

DEFAULT_GUIDELINES = (
    "- Work strictly from physical evidence; separate what is proven from what is inferred.\n"
    "- Non-destructive default: /usr/share/omarchy is immutable; user overrides belong in ~/.config with backups.\n"
    "- Zero-polling physics: use event streams, DBus signals, or IPC pushes; never poll on timers.\n"
    "- Purposeful motion: ceilings < 300ms, asymmetric 2/3 exits, tokenize with Style.duration(ms).\n"
    "- Native app ergonomics: separate C++ logic from QML UI; expose headless CLI commands."
)


def format_prompt(
    task: str,
    *,
    context: str | None = None,
    constraints: str | None = None,
    role: str | None = None,
    workspace: str | None = None,
) -> dict:
    """Format an agent task brief according to canonical JARVIS/Omarchy invariants."""
    clean_task = task.strip() if isinstance(task, str) else ''
    if not clean_task:
        raise ValueError('Task must be a non-empty string')

    lines = ["Task", clean_task, ""]

    if context and context.strip():
        lines.extend(["Evidence & Context", context.strip(), ""])

    guidelines = ROLE_GUIDELINES.get(role, DEFAULT_GUIDELINES) if role else DEFAULT_GUIDELINES
    lines.extend(["Operating Principles (JARVIS / Omarchy Style)", guidelines, ""])

    lines.extend([
        "Expected Result",
        "- Implement the required functionality, investigation, or diagnosis",
        "- Run relevant checks and automated tests with explicit output evidence",
        "- Report changed files and remaining limitations",
        "",
        "Constraints",
        "- Do not modify locked voice core files (audio/engine.py, audio/downstream.py, audio/echo_cancel.py)",
    ])

    if workspace and workspace.strip():
        lines.append(f"- Work strictly within the designated workspace: {workspace.strip()}")

    if constraints and constraints.strip():
        lines.append(f"- {constraints.strip()}")

    lines.append("- Never make unverified completion claims")

    formatted_text = "\n".join(lines).strip()
    return {
        'status': 'success',
        'task': clean_task,
        'role': role or 'general',
        'formatted_prompt': formatted_text,
        'style': 'jarvis-omarchy-invariants',
    }
