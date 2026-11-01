"""Compact routing plus on-demand bundled Omarchy topic guides."""
from pathlib import Path
import re

ROUTING = """
OMARCHY DESKTOP SKILL:
For volume, output mute, mic mute, brightness, night light, stay-awake/idle,
do-not-disturb, bluetooth, touchpad, status bar, and workspace requests, prefer
system_control: it reads state, acts and verifies in one call. Do not run discovery
for these known controls. Use signed percentage points for relative changes; use
workspace_back for 'go back' after a switch. Set binary controls with enabled=true/false
or call the corresponding toggle action. Do not substitute a toggle when the user
requested an explicit state.
For other unfamiliar Omarchy actions, discover routes with omarchy_help(topic=commands),
then command_details for exact arguments. Use omarchy_cli without a leading
'omarchy'. Use system_query for current facts, hypr_query before targeted window
operations, hypr_dispatch for workspaces/windows and launch_app for desktop apps.
Use omarchy_help(topic=skills) for the bundled Omarchy guides: themes, Hyprland,
plugins/bar, hooks, capture and user configuration. Read the matching guide before
customization. Discover current shortcuts before changing any binding. SUPER+H
belongs exclusively to linux-voice dictation and must remain untouched.
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
    for name in ('SKILL.md', 'hyprland.md', 'plugins.md', 'theming.md', 'hooks.md', 'capture.md', 'contributing.md'):
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
