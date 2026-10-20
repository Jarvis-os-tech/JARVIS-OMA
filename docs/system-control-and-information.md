# System controls and live information

JARVIS exposes fresh system observations separately from requested setting changes.
The integration uses the installed `ac.control-panel` scripts where their actions
are useful, and native readback to verify results. The installed plugin and stock
Omarchy files are not modified by this integration.

## Ask JARVIS

- “What is my current CPU usage and memory usage?”
- “How much free disk space is there?”
- “What CPU and GPU hardware can you actually detect?”
- “What are the current temperatures?”
- “Which displays and network interfaces are connected?”
- “Check the current volume, brightness and Do Not Disturb setting.”
- “List my audio outputs,” then select an exact listed output.
- “Check my user services,” then name the exact service to start or stop.
- “List installed themes,” then choose a theme by its installed name.

## Observation tools

`get_system_information(section="overview", detail=None, limit=10)` reads current
state every time it is called. The legacy `get_system_resources()` name calls the
same overview. Its result now uses the evidence envelope below rather than the
old flat metrics, which mislabeled normalized load average as CPU utilization.

| Section | Source and scope |
| --- | --- |
| overview | OS, CPU, memory, disk and battery child observations |
| cpu | Aggregate `/proc/stat` utilization sampled over approximately 150 ms; load averages reported separately |
| memory | `/proc/meminfo`, including actual available memory and swap counters |
| disks | Filesystem capacity and free space for an absolute path, default `/` |
| battery | Readable `/sys/class/power_supply` battery fields; per-field failures preserved |
| temperatures | Readable thermal-zone sensors with Celsius units |
| hardware | CPU model/count and GPU PCI vendor/device IDs; GPU marketing names are not guessed |
| os | OS release, kernel and uptime |
| network | Interface state and addresses; this does not prove internet reachability |
| displays | Current Hyprland monitor geometry, scale and refresh rate |
| audio | Default output volume and mute state |
| services | Current-user systemd units; optional exact unit details |
| processes | Process names, resident memory and lifetime CPU seconds; no command lines or environment |
| packages | Installed package names and versions from pacman |

Information results contain `observed_at` in UTC, `sources`, `status`, `data` and
`errors`. A successful measurement is a point-in-time observation, not a lasting
health guarantee. Overview observations have their own child timestamps because
CPU sampling and other reads finish at different times. `partial`, `unavailable`
or null values are not replaced with zero, a default or remembered information.

`get_system_control_status(category="all")` reads control state and discovers the
installed plugin and its executable scripts. Categories are audio (output and
microphone), display (brightness and night light), network, Bluetooth, power,
notifications and theme. Each observation reports its timestamp, source and
verification state. A plugin being installed does not prove every backend works.

## Control behavior

- Audio, microphone, brightness, explicit night-light state, Wi-Fi radio,
  Bluetooth connection, DND, named themes and power profiles use readback before
  reporting confirmed success.
- Explicit on/off requests are idempotent. They do not blindly toggle a setting.
- Plugin scripts can suppress command errors, so a zero exit code alone does not
  establish that a setting changed.
- Some actions, such as initiating Wi-Fi association, Bluetooth discovery,
  notification dismissal or suspend, can only be reported as requested or
  unverified when the resulting effect cannot be observed reliably.
- Themes are installed names. A generic dark/light toggle is not invented.
- The plugin's combined gaming preset is not advertised as verified because its
  component operations can fail independently. Individual supported controls
  remain available.

The `system_control_extension(category, action, target=None)` tool adds:

| Category | Actions |
| --- | --- |
| audio_output / audio_input | list, status, set_default using an exact freshly discovered native device name |
| user_service | list, status, start, stop, restart for an exact canonical user `.service` unit |
| media | list, status, play, pause, play_pause, stop, next, previous using an exact player |

Media requires `playerctl`. Missing optional commands return `unavailable`; they
are not silently installed. Service control uses only the user scope and never
constructs arbitrary shell commands. Audio and service changes are verified by
fresh state; media track/toggle requests may remain unverified.

## Accuracy and responsiveness

The voice instructions require a fresh relevant tool reading for each new system
question, including when a custom assistant prompt is configured. They prohibit
inventing missing readings, treating load as utilization, claiming internet
reachability from a local interface, or presenting an unverified change as done.
Device names, package text and other command output remain untrusted data.

Proc/sysfs reads run outside the voice event loop. New command paths use fixed
argument arrays, bounded output, timeouts and cleanup. No new runtime Python
dependency or local inference model is required. `pytest-asyncio` is a test-only
dependency for asynchronous regression coverage.

Verification combines deterministic failure/readback tests and live read-only
queries. Live system readings verify retrieval; mocked mutation tests do not
prove every setting change works on every desktop or device. The voice model's
adherence to evidence still requires observation during real conversation.
