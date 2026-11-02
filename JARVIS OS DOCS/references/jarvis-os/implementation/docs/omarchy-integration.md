# Omarchy skill integration

JARVIS uses the bundled Omarchy skill and six topic guides through its existing
control adapter. The recurring voice instruction contains compact routing only;
the full guides are read on demand with `omarchy_help` topic `skills`.
The guide sources and copy date are recorded in
`jarvis_control/omarchy_guides/PROVENANCE.md`.

## Available paths

| Request | Runtime tool |
| --- | --- |
| Common volume, mute, brightness and workspace requests | `system_control`: read, act and verify in one call |
| Find an installed command | `omarchy_help`: `commands` then `command_details` |
| Learn how to customize an area | `omarchy_help`: `skills`, query theme, Hyprland, plugins, hooks or capture |
| Current shortcuts and applications | `omarchy_help`: `shortcuts`, `applications` |
| User config locations, plugins and hooks | `omarchy_help`: `configuration`, `plugins`, `hooks` |
| Execute a supported stock command | `omarchy_cli`, using the discovered route without the leading `omarchy` |
| Window/workspace state and actions | `hypr_query`, `hypr_dispatch`, `send_shortcut` |
| Current system information | `system_query` |
| Public web information | `web_search`, `open_page`, with bounded public HTML/plain-text fetching and visible-browser fallback |

Discovery reads the installed command catalogue, not a static list of commands
from the model. The live check found 369 public routes and Omarchy 4.0.6-1.
That inventory can change after updates. Guide search returned 70 document
sections in this installation.

## Behavior and boundaries

- `SUPER+H` stays dedicated to `linux-voice` dictation.
- Packaged `/usr/share/omarchy` files remain read-only; overrides belong in user config.
- Control policy remains active. A held action needs a new spoken turn with an
  actual matching confirmation transcript. The model cannot confirm its own request.
- Read-only help can describe a gated command without executing or holding it.
- Tool-call IDs are deduplicated so repeated provider messages do not repeat a
  desktop effect. Recent results are retained for a resumed session.
- Control work is serialized off the audio loop and drained on shutdown.
- Public-page reads do not copy browser cookies or overwrite the clipboard.
  DNS and HTTP share a hard process deadline. Private destinations and private
  connected peers are rejected by direct fetching; authenticated/dynamic pages
  use the existing browser path instead.
- Opening a page alone is not reported as a successful information lookup.
- `jarvis-voice --check` validates audio commands, Python dependencies and config.
  Installed shortcuts work from outside the repository.

## Say these to test

1. “What Omarchy commands can you use to control audio?”
2. “Find the Omarchy guide for changing themes.”
3. “What Omarchy version is installed?”
4. “Which workspace am I on?”
5. “What time is it, and what is my timezone?”
6. “Open example.com and tell me what it says.”

The last check depends on network access. A timeout, verification challenge or
unreadable dynamic page must be reported as a failed lookup, without inventing
its contents. Microphone recognition and physical speaker quality still need
real listening checks.

See [verified system control](system-control.md) for direct voice phrases,
follow-ups, execution outcomes and the latest live checks.
