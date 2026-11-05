# 05 — Delivery and acceptance

Status: future implementation plan. No implementation or activation is authorized by preparing this package. No dates or completion percentages are asserted.

## Build packets

| Packet | Deliverable | Completion gate |
| --- | --- | --- |
| 0. Baseline and recovery | Identify active shell, voice owner, installed versions, current bindings, source/release and existing edits | Known-good normal desktop and voice; exact stop/restore path; no competing microphone owner |
| 1. Design validation | Review storyboards, scale, contrast, state copy, compact/canvas rules and exit | User can identify how to return from every scene; selected appearance documented |
| 2. Isolated presentation prototype | Synthetic-data viewer for modes, core and cards; no real tools/audio capture | Focus, multi-monitor, reduced-motion and exit work; mock data labelled |
| 3. Read-only real state | Gateway snapshot/stream, heartbeat, transcript, task/evidence data, measured envelopes | Offline/stale distinctions truthful; no fabricated telemetry; reload does not repeat actions |
| 4. Standard widgets and local controls | Timer/media/tasks/files/sources, real mute/interrupt/standby, typed fallback | Each operation has acknowledged state, matching receipt and clear failure behaviour |
| 5. Composed JIT and shared references | Tables, charts, comparisons, selection, voice edits, pin/restore | End-to-end comparison journey works; malformed/stale payloads rejected |
| 6. Native application integration | Browser/editor/file-manager handoff, compact return, conflicting automation pause | Correct resource/window verified; app focus restored; failed handoff retains card |
| 7. Recovery and release readiness | Restart, suspend, network loss, retention, resource budgets, package/version compatibility | Acceptance matrix passes on supported hardware; release activated with rollback |
| 8. Rich custom views (optional later) | Separate isolated web renderer and reviewed reusable-template registry | Confinement, crash containment, capabilities and resource limits proven before real data/tools |

Each packet includes a short evidence record with source revision, installed versions, hardware, data fixtures, measurements, failures and remaining limits. Existing master-plan voice/release blockers remain release gates; a polished GUI cannot waive them.

## First implementation boundaries

Start in a separate launchable preview using synthetic data. Keep desktop config, system services, bindings and production audio untouched until the relevant implementation scope is authorized. Any later desktop activation must have a named instance and a direct local return route, so stopping the preview never stops the normal shell.

Before activation, document the exact installed launcher, instance identifier, activation shortcut and rollback command based on the machine's actual versions. Avoid broad “kill all Quickshell” recovery. Never bind a fullscreen overlay with no independently reachable exit. The earlier accidental preview in this chat is the reason exit/recovery is a first-class acceptance gate.

## Acceptance matrix

| ID | Scenario | Pass condition |
| --- | --- | --- |
| A01 | Expand and return | Explicit activation opens chosen output; Return immediately restores desktop usability |
| A02 | Escape and focused widget | Escape closes local popup then canvas; Return remains one-step; emergency shortcut works independently |
| A03 | Wake while editing | Capture state changes visibly without unwanted fullscreen or keyboard grab |
| A04 | Compact identity | Time/battery/privacy readable; unknown battery honest; no weather/mic button |
| A05 | Mute and hardware mute | Actual acknowledged state shown; pointer/keyboard recovery exists; spoken unmute not required |
| A06 | Stop speaking versus cancel | Stop clears old audio only; Cancel stops only the identified task/owned workers with receipt |
| A07 | Spoken interruption | Opening words retained; old generation fenced; completed effects not repeated |
| A08 | Simple timer | Voice creates timer; follow-up updates right timer; dismissal/reload preserves timer |
| A09 | Research canvas | Progressive source/table/chart views use verified data, units and source dates |
| A10 | Deictic follow-up | “These rows” binds actual selected IDs/revision; ambiguous “that” asks a focused question |
| A11 | Live updates while reading | Selection, draft and scroll stay stable; cards do not expire or reorder under interaction |
| A12 | Widget lifecycle | Informational feedback expires appropriately; approval/task/pinned/draft remains recoverable |
| A13 | Pin versus template | Pin retains instance; reusable draft validation is separate; no permissions carried over |
| A14 | Native handoff | Correct resource in correct app verified; collapse follows success; failure keeps useful context |
| A15 | User takes over | Conflicting automation pauses; fresh observation required before resume |
| A16 | Network/provider failure | Local exit/mute remain available; independent local work continues; no blind side-effect replay |
| A17 | Stale state/telemetry | Dead service detected by heartbeat; old nonzero meter decays and becomes unavailable |
| A18 | Reconnect/restart | Snapshot/cursor consistent; duplicates/out-of-order rejected; views restored without actions replaying |
| A19 | Approval freshness | Approval names target/effect; expired or changed action cannot execute under old approval |
| A20 | Malformed/hostile payload | Invalid component/action/asset/size rejected; trusted native frame and exit survive |
| A21 | Accessibility | Keyboard operation, 200% text, reduced motion/transparency, contrast and actual assistive stack checked |
| A22 | Multiple outputs | Mixed scaling, negative coordinates, output unplug and focus changes keep content/exit reachable |
| A23 | Lock/suspend | Sensitive canvas hidden; no spoken private result on lock; no automatic side-effect replay on resume |
| A24 | Heavy load | Audio quality preserved while visual frames drop; renderer recovers to current state |
| A25 | Rich renderer fault | Later renderer crash/hang/resource violation cannot take audio/control/exit down |
| A26 | Retention/deletion | Saved views/drafts and provenance follow retention policy; forgetting removes eligible retained data |
| A27 | Focused voice-only composition | No app dock, launcher rail, persistent helper panel or unrelated dashboard content; only task-relevant widgets appear |

## Proposed performance budgets

Targets measured on the supported machine, not promises or claims about existing code. Report p50/p95 and the tested workload.

| Measurement | Initial target / evaluation |
| --- | --- |
| Local exit input → input release | p95 ≤100ms; fade may finish later |
| Admitted known payload → first meaningful standard/composed frame | p95 ≤100ms; ≤50ms stretch target for small warm native views |
| Live audio sample age at presentation | p95 ≤150ms; visibly stale/decay around 250ms |
| Control request → acknowledged presentation | p95 ≤250ms for available local service; show pending on slow response |
| Heartbeat loss → stale indication | Around 6 seconds with 2-second heartbeat; tune under suspend/load |
| Active animation | Aim for display refresh; validate 60Hz workload and graceful fallback |
| Background/idle visual activity | No continuous decorative loop; stop hidden audio/render polling |
| Large-result handling | 100 visible table rows/page, chart decimation, bounded payloads and assets |
| Audio impact | Compare underruns/dropouts and interruption latency against voice-only baseline under equivalent load |
| Memory/CPU/GPU/power | Measure cold/warm/idle/6-card/rich-view scenarios; set release ceilings after baseline, record hardware |

End-of-speech to answer time includes provider/tool work and is measured separately. Never present a <50ms rendering budget as total voice-request latency. Distinguish accepted interruption, audible stop and provider acknowledgement.

## Measurement method

Timestamp input, admission, task start, payload-ready, first frame, action acknowledgement, verified outcome and audio boundaries. Correlate with request/generation IDs. Keep measurements local and redact transcript/path content from ordinary performance logs. Use repeatable synthetic fixtures plus actual microphone/speaker and desktop workflows. Software tests cannot prove acoustic interruption or readable multi-monitor placement.

## Release checklist

All applicable acceptance cases pass with evidence. No startup binding errors in the active presentation path. Capture/permission labels match real state. System shortcuts remain available. Local exit works with provider disconnected and rich view hung. Release/version/schema compatibility and rollback are checked without rolling back newer user data. Production changes are separately authorized and scoped.

## Decisions for later implementation

The broad stack and appearance are settled as proposals. Version-check the deployed Quickshell/Qt/Hyprland before selecting APIs. Choose the isolated rich-renderer technology only when its need and confinement are demonstrated. Pick an activation shortcut after inspecting existing bindings; keep Super+H. Choose data retention defaults through the existing JARVIS privacy settings. Set hardware-specific resource ceilings from measured baselines.
