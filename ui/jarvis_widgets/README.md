# Widgets inside the existing JARVIS shell

This extension loads into the running Omarchy/Quickshell desktop. It reuses the
existing Dynamic Island and voice service. It has no separate shell, island,
dock or background GUI process. It starts hidden.

## Available surfaces

- Generated views: JARVIS composes a new layout for the task, including nested
  rows/columns, text, headings, values, editable fields, sliders, switches,
  choices, action buttons and data-bound diagram shapes.
- Controls update local state and calculations immediately. Button actions send
  the user's chosen values and widget ID into the existing JARVIS conversation.
- Floating widgets are the default; a nonmodal grouped canvas is optional.
  The desktop stays available, and keyboard focus is acquired on interaction.
- Native input bar: submit text to the current voice session. Rejected requests
  keep their draft and show an error. Acceptance means queued, not completed.
- Cards: text, local images, generic QR codes, silent local video PiP, tables,
  bar charts and measured or indeterminate progress. An existing widget ID
  updates that card instead of creating another.

There are no Esc/Return navigation controls or pin/float/dismiss toolbar buttons.
JARVIS handles “close that”, “keep this”, “move it” and “clear the widgets” using
the management tools. An omitted ID resolves to the last interacted/latest
widget; status exposes titles, IDs and current control state for explicit
references. The close command hides all surfaces; clear_all removes all widgets.
Pins, state and drafts currently last for the shell session only.
The input bar supports text; file attachments remain a separate existing flow.

## Use from any terminal

After installing the managed voice extension:

```sh
jarvis widgets open
jarvis widgets input
jarvis widgets close
jarvis widgets status
```

The workspace controller also works without installing a new voice release:

```sh
"/home/g0pi/JARVIS OS/bin/jarvis" widgets input
omarchy-shell jarvis-canvas close
```

## Installation status · 2026-11-02

Plugin v0.2.0 is installed at `~/.config/omarchy/plugins/jarvis.widgets`.
The live handler reports `engine: composed-v1`, hidden with no sample widgets.
Hot rescan retained the old cached renderer; one refresh of the existing shell
loaded the new code. The latest settings/plugin backup is
`~/.config/omarchy/backups/jarvis-widgets-20261102-230305-rg97tcjf`.

The widget voice adapters are active in managed release
`20261102T172816Z-existing-shell-widgets`, based on the previously active
`20261102-223701-situational-acknowledgements` build. All four widget tools were
confirmed in the live registry, and widget_schema completed through the running
voice service. The previous release remains available for rollback.

An extra voice reported during verification was traced to cached acknowledgements
labelled offline-espeak-ng. Local cached fillers were disabled in the user's
voice config; the main Aoede voice was preserved. This is a user configuration
change, independent of widget rendering.

Example of a generic floating QR card:

```sh
jarvis widgets show qr --title "Example link" --floating \
  --data '{"content":"https://example.org"}'
```

Use `--data-file` for private JSON rather than placing its content in command
arguments. Pairing credentials must come from the existing pairing service;
this renderer does not create them. Media must already be a supported local
file. The existing camera and screen capture flows remain separate.

## Voice integration

The core voice catalogue supplies `widget_schema`, `show_widget`, `manage_canvas`
and `manage_widget`. JARVIS first reads widget_schema, then builds a kind=view
payload containing `{state, computed, layout, width}`. Expressions are structured
references/arithmetic; text supports `{{key}}` bindings. Shapes use a 0–1000
coordinate space. See view_schema.py for the contract and an example estimator.
Those example values are test fixtures, not real measurements.

Reuse widget_id to replace/refine a layout, querying current state first to keep
user edits. manage_widget supports move with x/y integer percentages 0–100.
Pin protects against expiry; hovering or keyboard focus also defers expiry.
`open_input_bar` opens the original attachment-capable JARVIS input bar.
The canvas text field remains available explicitly through `jarvis widgets input`;
installing this plugin does not replace JARVIS's multimodal input bar.

Views contain validated data rendered by known components. Arbitrary generated
QML, HTML/JavaScript, screen capture, persistent template promotion and automatic
app handoff are future work. Showing a card grants no permission to perform a
system action. No new audio capture or audio-processing engine is added here.

## Install and verify

```sh
python3 scripts/install_widget_plugin.py --apply
python3 scripts/check_widget_plugin.py
```

The installer backs up shell settings and any previous copy of this plugin,
preserves existing settings/plugins, and rescans the running shell. It does not
restart Quickshell. The smoke check opens three clearly labelled sample cards,
checks the input surface, then removes its samples and hides all surfaces. It
refuses to run if user cards or a surface are already active.

```sh
python3 scripts/prepare_widget_release.py --prepare /tmp
# Use the exact prepared directory printed above:
python3 scripts/prepare_widget_release.py --activate /tmp/jarvis-widgets-release-...
```

The optional managed-release step copies the active installed build and applies
only widget integration changes. It checks manifests and hashes before switching
the release, then restarts the voice/device services with health rollback. It
retains earlier releases. It does not deploy unrelated workspace changes.

Focused checks cover data validation, real QR output, installer preservation,
registry loading, generated nested layouts/diagrams, real control interaction,
calculation updates, action payloads, draft retention, pins and expiry. Latest
results: 12 Python tests with 10 subtests and 14 Qt checks pass. Physical
microphone-to-widget interaction still needs a spoken session check; no model
generation or audible test was started during this installation.
