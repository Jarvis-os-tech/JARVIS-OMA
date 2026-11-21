"""Compact routing plus on-demand bundled Omarchy topic guides."""
from pathlib import Path
import re

ROUTING = """
OMARCHY DESKTOP SKILL:
For volume, output mute, mic mute, brightness, media playback (play, pause, next, previous, status),
window controls (window_close, window_fullscreen, window_toggle_float, window_center, window_pin,
and window_focus by name with target="app"), night light, stay-awake/idle, do-not-disturb,
bluetooth, touchpad, status bar, and workspace requests, prefer system_control: it reads state,
acts and verifies in one call. Do not run discovery for these known controls. Use signed percentage
points for relative changes; use workspace_back for 'go back' after a switch. Set binary controls
with enabled=true/false or call the corresponding toggle action. Do not substitute a toggle when the
user requested an explicit state.
For unfamiliar Omarchy actions, discover routes with omarchy_help(topic=commands),
then command_details for exact arguments. Use omarchy_cli without a leading
'omarchy'. Use system_query for current facts, hypr_query before targeted window
operations, hypr_dispatch for workspaces/windows and launch_app for desktop apps.
Use omarchy_help(topic=skills) for the bundled Omarchy guides: themes, Hyprland,
plugins/bar, hooks, capture, crash diagnosis, and user configuration. Read the matching guide before
customization. Discover current shortcuts before changing any binding. SUPER+H
belongs exclusively to linux-voice dictation and must remain untouched.

CRASH DIAGNOSIS & RECOVERY PROTOCOL:
When an application or process crashes, segfaults, disappears, aborts, or dumps core:
1. Establish facts from coredumpctl info <pid> and coredumpctl list. Note the exact command line,
   crashing binary, process name, signal, and timestamp.
2. Rule out resource exhaustion first: check free -h and journal for OOM killer invocations.
3. Correlate timeline: inspect filesystem mtimes matching the crash second, journal warnings around
   the event, and recent package updates.
4. Read thread stacks to identify in-flight work and trigger frames. Symbolize via Arch debuginfod
   and gdb batch mode if helpful; write extracted cores to mktemp and delete immediately after use.
5. Report: 1) What crashed and what it was doing, 2) Likely mechanism (evidence vs inference),
   3) User data safety & recovery path (check trash), 4) Recurrence likelihood and verified fix.
6. Auto-remediation: repair configuration/cache/lock corruption when within reach. If recurring
   and unfixable immediately, offer omarchy-crash-mute '<program>' to silence notifications. If it is
   a verified Omarchy bug, follow upstream reporting rules with user confirmation.

PROMPTING & DELEGATION PROTOCOL (JARVIS / OMARCHY STYLE):
When delegating work to agents or prompting models:
- Format prompts with radical epistemic clarity: physical facts first, proven vs inferred separation, zero fluff.
- Mandate non-destructive boundaries: /usr/share/omarchy is immutable; user configs live in ~/.config with backups.
- Enforce zero-polling hardware rules: 4-tier event hierarchy (signals > shared pipes > FileView > CLI push).
- Enforce purposeful motion budgets: 0ms for instant jumps; <300ms for dwell surfaces; tokenized with Style.duration(ms).
- Mandate test verification: require explicit test outputs and changed file reports before claiming completion.
- Never touch locked voice core files (audio/engine.py, audio/downstream.py, audio/echo_cancel.py).

Package-owned /usr/share/omarchy is read-only. User overrides belong in ~/.config;
back up before edits and verify the documented reload. Prefer installed stock
commands. Never bypass tool policy or invent a command when discovery fails.
Config refresh resets customizations and needs the user's explicit confirmation.
Ordinary clear desktop requests are permission to act; do not ask an extra
confirmation unless a tool requires one. For a named app/window, query the actual
windows, target its address, and verify it exists after launch or focus. For
multi-step requests, preserve dependency order; stop and replan when a step fails
or is held. A failed/not-run/unknown result is never a completed action. For
follow-ups, use the latest verified state and refresh it when needed. Ask one
brief question only when the target remains ambiguous. Give one concise spoken
acknowledgement with the observed result after finishing the requested work.
Privilege elevation, resets and destructive actions remain governed by tool policy;
do not try another route around a refused or held action. Report success only
when execution and its resulting state have been verified.
"""


def guide_sections():
    root = Path(__file__).with_name('omarchy_guides')
    rows = []
    for name in ('SKILL.md', 'hyprland.md', 'plugins.md', 'theming.md', 'hooks.md', 'capture.md', 'contributing.md', 'crash.md', 'crash_reporting.md', 'prompt_style.md'):
        path = root / name
        if not path.is_file():
            continue
        chunks = re.split(r'(?m)^(?=##? )', path.read_text(encoding='utf-8'))
        for chunk in chunks:
            if not chunk.strip() or chunk.startswith('---'):
                continue
            heading = chunk.splitlines()[0].lstrip('# ').strip()
            rows.append((f'{name}: {heading}', chunk[:3000]))
    return rows
