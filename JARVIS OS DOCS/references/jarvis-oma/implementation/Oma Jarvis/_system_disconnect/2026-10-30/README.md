# JARVIS disconnected — 30 October 2026

JARVIS is stopped and detached from the desktop. Its code, organized copy, installed plugin code, credentials and saved data remain in place.

Changes made:

- Stopped/disabled `jarvis-oma.service` and persistently masked it to prevent startup. The original installed service file is backed up here.
- Disabled the JARVIS Dynamic Island, Aura Orbit and Vision PiP plugins. Standard Omarchy notifications and on-screen volume/brightness feedback were enabled to replace the island's desktop feedback.
- Detached the JARVIS login hook, application-menu launcher, and `jarvis` / `jarvisctl` PATH symlinks. Their original contents/targets are saved here.
- Disabled the JARVIS voice, configuration and island hotkeys and reloaded the desktop bindings.
- Detached and archived systemd sleep wake drop-ins (`restart-jarvis-gateway.conf`, `restart-jarvis-agent-bus.conf`, `restart-jarvis-yt-brain-worker.conf`) to prevent automatic startup on wake.
- Archived inactive JARVIS plugins (`omarchy-jarvis-island`, `omarchy-ai.orbit`, `omarchy-ai.vision-pip`) from `~/.config/omarchy/plugins/` to backup storage without deleting any files.

Six automated live checks passed. Verification found zero running JARVIS-project processes, zero JARVIS hotkeys, and an inactive/masked service with PID 0. The 3,607 inventoried project/copy/plugin files retained their contents and permissions. The original voice-lock verifier also passed for all seven locked files.

The separate PMA/Omarchy Voice service, voice indicator, voice shortcut, Hermes assistant and other services were not disabled. No provider credentials were revoked, so JARVIS can reconnect later without deleting its saved account configuration. This disconnect prevents the installed JARVIS entry points from running; deliberately launching source code directly remains possible.

## Reconnect later

First check that the saved settings can still be restored safely:

```sh
python3 '/home/g0pi/Projects/JARVIS-OMA/Oma Jarvis/_system_disconnect/2026-10-30/reconnect.py'
```

To restore JARVIS desktop integration and start the service:

```sh
python3 '/home/g0pi/Projects/JARVIS-OMA/Oma Jarvis/_system_disconnect/2026-10-30/reconnect.py' --apply --start
```

Add `--enable-login` only if you also want JARVIS to start automatically at login. Before this disconnect, the main service was already stopped and disabled; `--apply` alone restores the desktop integration while leaving it stopped.

The restore script refuses to overwrite settings changed after disconnection. If it reports conflicts, merge the JARVIS-specific settings from the saved files instead. The former login hook references a script already missing before disconnection; restoring that hook preserves its prior state but does not repair it.

The restore script has only been checked in its no-change mode; JARVIS has not been restarted to test restoration.

## Saved evidence

- [Original settings, targets, hashes and verification state](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_system_disconnect/2026-10-30/manifest.json)
- Original configuration files are in `files/`, protected by this directory's owner-only permissions.
- [Live disconnection tests](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/_system_disconnect/2026-10-30/verification.xml)
