# Foundation repair: 2026-10-19

## Confirmed runtime cause

The running systemd service lacked WAYLAND_DISPLAY, DISPLAY, and
HYPRLAND_INSTANCE_SIGNATURE. Its journal showed failed application launches,
window queries, and desktop observation. The interactive desktop had valid
session values. Importing those values and restarting restored desktop access.

`run.sh` now recovers missing Wayland and Hyprland identifiers from unique
runtime socket nodes. Explicit values are preserved. Multiple sessions remain
ambiguous and require explicit environment configuration; socket existence is
not a guarantee that the compositor is responsive. X11 DISPLAY is not inferred.

## Changes and evidence

Final combined verification: `JARVIS_TEST_SANDBOX=1 .venv/bin/python -m pytest
-q --durations=5` completed with **527 passed and 180 subtests passed in 23.45
seconds**, with no skips or warnings. This includes the two real sandbox checks.

- Built `skills/native/bin/vision_ctrl` using `make -C skills/native`.
  Its status action reports camera ready, display ready, and PipeWire present.
  This proves hardware discovery, not camera image delivery.
- Restarted JARVIS; the journal reaches LIVE and binds audio streams to AEC.
  Camera tools are no longer excluded for a missing executable.
- Window query using the service session variables returns exit status zero.
- JARVIS `open_application` successfully opens Files.
- JARVIS GUI observation captures a 1920x1080 PNG through the driver.
  No mouse, typing, or model image comprehension was verified.
- GUI driver startup errors now become structured GuiControlError failures.
- Fixed a memory integration test race: queued voice writes must finish before
  checking persistence or deleting the temporary database. All eight memory
  integration tests pass. This was not evidence of broken production SQLite.
- Startup, GUI, and memory regression selection: 27 passed.
- System-control and vision selection: 21 passed.
- Dynamic skill selection: 32 passed, 11 subtests passed.
- The full-suite timeout was traced to the Google OAuth launch test creating a
  real thread around a mocked HTTP server. Its request loop spun for five
  minutes. The launch test now mocks thread startup and checks it was invoked;
  separate callback-loop tests continue to test callback behavior.
- The opt-in real sandbox checks exposed a missing Python runtime mount.
  Verification now mounts the external Python installation and its version
  alias read-only, without exposing their containing home directory. Real
  isolation checks and the development pipeline pass with temporary fixtures.
- Pytest discovery targets this project's tests and excludes preserved upstream
  sources. Test credentials, runtime directory, and executable search paths
  are isolated. The runtime directory isolation prevents camera tests writing
  into the user's real session directory.
- CI uses the same pytest entry point, with an overall timeout.

The previous inference that executable discovery was the root cause of the
long full-suite timeout was incorrect. The captured traceback identified the
runaway mocked OAuth server thread; test environment isolation remains useful
but did not by itself resolve the timeout.

## Corrections to the earlier audit

The project virtual environment contains numpy, httpx, pytest, google.genai,
and sounddevice. Missing imports reported by agents using system Python do not
establish a broken project installation. Upstream `openjarvis` bundle tests are
not the supported application test suite.

## Still requires evidence

Live browser automation, all GUI input routes, external account authentication,
long-running agent execution, and voice-to-action acceptance remain unverified.
The earlier cloud reconnect errors require observation over time; a successful
LIVE connection does not establish that connection failures are eliminated.
The startup AEC warning is followed by successful explicit stream binding, but
perceived echo cancellation quality still requires a listening test.
