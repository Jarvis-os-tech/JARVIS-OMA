# JARVIS OMA Master Document

Status: Integration specification and migration boundary  
Updated: 2 November 2026  
Parent product: [JARVIS OS](../../../../JARVIS_OS_FINAL_MASTER.md)

## 1. Purpose

JARVIS OMA is the compatibility and control layer between Omarchy and JARVIS.
Its job is to make Omarchy discoverable, controllable, and explainable through
voice without pretending that the language model is the operating system.

The layer must:

1. discover the installed Omarchy version, commands, applications, shortcuts,
   configuration locations, and guides;
2. expose safe desktop actions through typed tools with observable results;
3. keep policy, confirmation, dry-run, and denial rules outside model prose;
4. preserve Omarchy updateability by keeping packaged files read-only; and
5. provide a stable contract so the JARVIS OS layer can evolve independently.

## 2. Current implementation baseline

The repository already provides:

- `jarvis_control` for discovery, desktop control, browser retrieval, tasks,
  vision, policy, diagnostics, and the unified skill router;
- `system_control` fast paths for audio, brightness, night light, idle mode,
  notifications, Bluetooth, touchpad, bar visibility, and workspaces;
- on-demand Omarchy guides with recorded provenance;
- a protected local control socket and CLI entry points;
- durable task submission and status inspection;
- browser reads with private-network and cookie boundaries; and
- voice attachment through `UnifiedSkills`.

The live installation has previously been checked against Omarchy 4.0.6-1 with
369 discovered public routes and 70 guide sections. That inventory is dynamic;
it must be regenerated after an Omarchy update.

## 3. Contract with Omarchy

### Read-only discovery

Discovery reads the installed command catalogue and current desktop state. It
must never assume that a command exists because a model remembers it. Help and
guide retrieval are read-only and may explain a gated command without running it.

### Typed actions

Every mutating action is represented by a typed tool with:

- normalized arguments;
- an explicit policy decision;
- a dry-run representation;
- an execution result;
- post-action verification; and
- a concise spoken summary.

### Safety boundary

The model may request an action, but it cannot authorize its own request.
Held actions require a genuinely new confirmation transcript. Duplicate tool
call IDs must be idempotent. A failed action stops dependent actions in the same
batch so JARVIS can inspect and re-plan.

### Update boundary

JARVIS may read Omarchy's installed guides and command catalogue. It must not
edit packaged Omarchy files. Customization belongs in user configuration,
documented overlays, or supported Omarchy commands.

## 4. Voice interaction contract

Typical requests include:

- “What Omarchy commands can control audio?”
- “Set the volume to forty percent.”
- “Which workspace am I on?”
- “Switch to workspace two, then tell me what changed.”
- “Find the guide for changing themes.”
- “Open example.com and tell me what it says.”

JARVIS should answer read-only questions directly, perform ordinary supported
actions with verification, ask one short clarification when a target is
ambiguous, and request confirmation only when policy requires it.

## 5. Operational checks

```sh
bin/jarvis control list
bin/jarvis control call system_query '{"topic":"time"}'
bin/jarvis control call launch_app '{"app":"firefox"}' --dry-run
jarvis doctor --json
```

After Omarchy updates, regenerate discovery and repeat read-only checks before
enabling new mutating routes. Keep the original Omarchy attribution and
provenance records intact.

## 6. Known limits

- A successful page open is not proof that page contents were retrieved.
- Private destinations and browser-authenticated content need the browser path.
- Physical microphone recognition and speaker quality require real listening
  checks; software tests cannot prove them.
- Durable native tasks and external agent jobs have separate cancellation and
  ownership today; future work should unify parent/child cancellation.

## 7. Exit criteria for the OMA layer

JARVIS OMA is release-ready when a fresh installation can discover the current
Omarchy surface, perform verified read-only and low-risk actions by voice, hold
and confirm risky actions correctly, survive a restart without losing durable
task records, and pass the full regression suite plus a real microphone/speaker
conversation check.
