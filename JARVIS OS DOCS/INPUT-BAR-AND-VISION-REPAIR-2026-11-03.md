# JARVIS input bar and vision repair

Date: 3 November 2026.

## Reported behavior and cause

The JARVIS `open_input_bar` adapter had been changed to prefer the optional canvas plugin's text-only input field. This replaced the original compact WebKit input bar whenever the plugin was available and removed the visible attachment workflow. The matching close adapter also returned after closing the canvas field, leaving any original input bar/server open.

Vision source inspection found missing `shutil` and `subprocess` imports in the voice daemon. Cold frame-capture fallback and immediate preview broadcasts referenced those modules. Background exception handling could hide the resulting failures. Vision control also required specialist tool discovery instead of being attached directly to the everyday voice catalog.

## Applied repair

- Restored the original attachment-capable bar as the default `open_input_bar` behavior. The separate canvas remains explicitly available.
- Close both the optional canvas input and the original input-bar server/window.
- Added the missing voice-runtime imports.
- Attached `control_vision_mode` directly to the live tool catalog.
- Added camera/capture dependency checks before changing mode, and structured IPC errors for unavailable vision inputs.
- Preserved the active installed build and applied only four runtime file changes through a staged release; unrelated working-tree edits were not deployed.

Installed release: `/home/g0pi/.local/share/jarvis-runtime/releases/20261103T160238419426Z-input-vision-repair`.

Previous release retained: `/home/g0pi/.local/share/jarvis-runtime/releases/20261103T123444785625Z-system-integration`.

The activation metadata is under `input_vision_repair` in the installed `release.json`. The reproducible preparation helper is `scripts/prepare_input_vision_repair.py`.

## Verification and limits

- Focused regression run: 37 passed and 10 subtests passed, covering widget routing, close cleanup, vision fallback with synthetic frames, frame delivery to a fake session, missing-camera errors, live-tool declarations and local IPC.
- Additional input-forwarding checks: 3 passed, covering typed requests, mocked web content, code attachments and image attachments using fake conversational sessions. Together the successful runs cover 40 tests and 10 subtests. Restricted-environment attempts timed out; the checks passed when rerun with normal local sockets/threading available.
- Staged definitions validated before activation; release health checks passed.
- A real `open_input_bar` call through the running service returned text/image/audio/PDF/file support. Hyprland reported the mapped `JarvisInputBar` window at 600 × 50 pixels.
- The bar's own loopback page was reachable and contained the original file attachment, 10 MiB limit and drag/drop controls. No synthetic request or attachment was sent to the real conversational model.
- With the user's explicit permission, the live preview control switched screen vision on, generated a fresh JPEG, and restored the previous off mode. This proves control and frame capture, not the accuracy of a model's interpretation.
- The service reconnected successfully after restart, then returned to the user's pre-existing standby state. The later preview check ran while standby was preserved, so that particular check does not prove cloud frame delivery.
- Host inventory showed `/dev/video0` and `/dev/video1`; actual camera capture was not tested. Missing-camera behavior was tested with mocks, not inferred from the restricted execution environment.

Final state: original input bar left open, vision restored to off, pre-existing standby preserved.
