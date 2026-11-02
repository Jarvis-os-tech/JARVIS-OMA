# voice

Voice capture, speech turns, interruptions, response handling, playback, latency, echo cancellation and recovery.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [backends/native](backends/native/FEATURE.md)
- [backends/native/native_sources](backends/native/native_sources/FEATURE.md)
- [backends/pipewire](backends/pipewire/FEATURE.md)
- [capture](capture/FEATURE.md)
- [controls](controls/FEATURE.md)
- [diagnostics](diagnostics/FEATURE.md)
- [echo_cancellation](echo_cancellation/FEATURE.md)
- [echo_cancellation/compatibility](echo_cancellation/compatibility/FEATURE.md)
- [extensions](extensions/FEATURE.md)
- [fast_response](fast_response/FEATURE.md)
- [first_speech_output](first_speech_output/FEATURE.md)
- [first_token_processing](first_token_processing/FEATURE.md)
- [greetings](greetings/FEATURE.md)
- [integrity](integrity/FEATURE.md)
- [interruptions](interruptions/FEATURE.md)
- [playback](playback/FEATURE.md)
- [recovery](recovery/FEATURE.md)
- [response_latency](response_latency/FEATURE.md)
- [session](session/FEATURE.md)
- [standby](standby/FEATURE.md)
- [turn_detection](turn_detection/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `audio/.voice_lock.json` | [integrity/.voice_lock.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/integrity/.voice_lock.json) |
| `audio/README.md` | [docs/original_audio/README.md](../../audio/README.md) |
| `audio/__init__.py` | [extensions/package_markers/audio/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/extensions/package_markers/audio/__init__.py) |
| `audio/downstream.py` | [first_speech_output/downstream.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/downstream.py) |
| `audio/echo_cancel.py` | [echo_cancellation/echo_cancel.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/echo_cancel.py) |
| `audio/engine.py` | [backends/native/engine.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/engine.py) |
| `audio/extension.py` | [extensions/extension.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/extensions/extension.py) |
| `audio/plugins/__init__.py` | [extensions/package_markers/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/extensions/package_markers/__init__.py) |
| `audio/plugins/native/.gitignore` | [backends/native/native_sources/.gitignore](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_sources/.gitignore) |
| `audio/plugins/native/Makefile` | [backends/native/native_sources/Makefile](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_sources/Makefile) |
| `audio/plugins/native/README.md` | [backends/native/native_sources/README.md](../../../../jarvis-os/implementation/audio/plugins/native/README.md) |
| `audio/plugins/native/companion.c` | [backends/native/native_sources/companion.c](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_sources/companion.c) |
| `audio/plugins/native/webrtc_gain.cpp` | [backends/native/native_sources/webrtc_gain.cpp](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_sources/webrtc_gain.cpp) |
| `audio/plugins/native/webrtc_gain.h` | [backends/native/native_sources/webrtc_gain.h](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_sources/webrtc_gain.h) |
| `audio/plugins/native/webrtc_gain_test.c` | [backends/native/native_sources/webrtc_gain_test.c](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_sources/webrtc_gain_test.c) |
| `audio/plugins/native_acceptance.py` | [diagnostics/native_acceptance.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/diagnostics/native_acceptance.py) |
| `audio/plugins/native_backend.py` | [backends/native/native_backend.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_backend.py) |
| `audio/plugins/native_probe.py` | [diagnostics/native_probe.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/diagnostics/native_probe.py) |
| `audio/plugins/pipewire_backend.py` | [backends/pipewire/pipewire_backend.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/pipewire/pipewire_backend.py) |
| `audio/plugins/spoken_interrupt.py` | [interruptions/spoken_interrupt.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/spoken_interrupt.py) |
| `audio/plugins/standby.py` | [standby/standby.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/standby/standby.py) |
| `core/agent.py` | [session/agent.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/agent.py) |
| `core/audio_scheduler.py` | [fast_response/audio_scheduler.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/fast_response/audio_scheduler.py) |
| `core/connection.py` | [recovery/connection.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/connection.py) |
| `core/greeting.py` | [greetings/greeting.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/greetings/greeting.py) |
| `core/monitor_echo.py` | [echo_cancellation/monitor_echo.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/monitor_echo.py) |
| `core/response_metrics.py` | [response_latency/response_metrics.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/response_latency/response_metrics.py) |
| `core/speech_turn.py` | [turn_detection/speech_turn.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/turn_detection/speech_turn.py) |
| `core/stable_echo_cancel.py` | [echo_cancellation/stable_echo_cancel.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/stable_echo_cancel.py) |
| `core/stable_recovery.py` | [recovery/stable_recovery.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/stable_recovery.py) |
| `core/stable_voice.py` | [session/stable_voice.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py) |
| `docs/browser-parity-audio-research-2026-10-21.md` | [docs/docs/browser-parity-audio-research-2026-10-21.md](../../../research/docs/browser-parity-audio-research-2026-10-21.md) |
| `docs/realtime-voice-audit-2026-10-15.md` | [docs/docs/realtime-voice-audit-2026-10-15.md](../../../evidence/docs/realtime-voice-audit-2026-10-15.md) |
| `docs/realtime-voice-deep-audit-2026-10-15.md` | [docs/docs/realtime-voice-deep-audit-2026-10-15.md](../../../evidence/docs/realtime-voice-deep-audit-2026-10-15.md) |
| `docs/superpowers/plans/2026-10-14-full-duplex-voice-os.md` | [docs/docs/superpowers/plans/2026-10-14-full-duplex-voice-os.md](../../../designs/docs/superpowers/plans/2026-10-14-full-duplex-voice-os.md) |
| `docs/superpowers/specs/2026-10-14-full-duplex-voice-os-design.md` | [docs/docs/superpowers/specs/2026-10-14-full-duplex-voice-os-design.md](../../../designs/docs/superpowers/specs/2026-10-14-full-duplex-voice-os-design.md) |
| `docs/superpowers/specs/2026-10-20-voice-core-lock-design.md` | [docs/docs/superpowers/specs/2026-10-20-voice-core-lock-design.md](../../../designs/docs/superpowers/specs/2026-10-20-voice-core-lock-design.md) |
| `docs/voice-capability-wiring.md` | [docs/docs/voice-capability-wiring.md](../../docs/voice-capability-wiring.md) |
| `echo_cancel.py` | [echo_cancellation/compatibility/echo_cancel.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/compatibility/echo_cancel.py) |
| `project-docs/AUDIO_OUTPUT_AND_LISTENING_FIX_2026-10-29.md` | [docs/project-docs/AUDIO_OUTPUT_AND_LISTENING_FIX_2026-10-29.md](../../../historical-plans/project-docs/AUDIO_OUTPUT_AND_LISTENING_FIX_2026-10-29.md) |
| `project-docs/GITHUB_VOICE_RESTORE_2026-10-28.md` | [docs/project-docs/GITHUB_VOICE_RESTORE_2026-10-28.md](../../../../jarvis-os/historical-plans/project-docs/GITHUB_VOICE_RESTORE_2026-10-28.md) |
| `project-docs/JARVIS_PERSONAL_VOICE_OS_MASTER.md` | [docs/project-docs/JARVIS_PERSONAL_VOICE_OS_MASTER.md](../../../historical-plans/project-docs/JARVIS_PERSONAL_VOICE_OS_MASTER.md) |
| `project-docs/PARALLEL_SPEECH_STREAMING_2026-10-28.md` | [docs/project-docs/PARALLEL_SPEECH_STREAMING_2026-10-28.md](../../../../jarvis-os/historical-plans/project-docs/PARALLEL_SPEECH_STREAMING_2026-10-28.md) |
| `project-docs/SPEECH_DETECTION_FIX_2026-10-28.md` | [docs/project-docs/SPEECH_DETECTION_FIX_2026-10-28.md](../../../../jarvis-os/historical-plans/project-docs/SPEECH_DETECTION_FIX_2026-10-28.md) |
| `project-docs/SPEECH_ONLY_RECOVERY_2026-10-28.md` | [docs/project-docs/SPEECH_ONLY_RECOVERY_2026-10-28.md](../../../../jarvis-os/historical-plans/project-docs/SPEECH_ONLY_RECOVERY_2026-10-28.md) |
| `project-docs/VOICE_RELIABILITY_FIX_2026-10-29.md` | [docs/project-docs/VOICE_RELIABILITY_FIX_2026-10-29.md](../../../historical-plans/project-docs/VOICE_RELIABILITY_FIX_2026-10-29.md) |
| `project-docs/VOICE_REPAIR_2026-10-28.md` | [docs/project-docs/VOICE_REPAIR_2026-10-28.md](../../../../jarvis-os/historical-plans/project-docs/VOICE_REPAIR_2026-10-28.md) |
| `project-docs/VOICE_TURN_PROTECTION_2026-10-28.md` | [docs/project-docs/VOICE_TURN_PROTECTION_2026-10-28.md](../../../../jarvis-os/historical-plans/project-docs/VOICE_TURN_PROTECTION_2026-10-28.md) |
| `scripts/verify_voice_lock.py` | [integrity/verify_voice_lock.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/integrity/verify_voice_lock.py) |
| `scripts/voice_diagnostics.py` | [diagnostics/voice_diagnostics.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/diagnostics/voice_diagnostics.py) |
| `skill_manifests/standby.json` | [standby/manifests/canonical/standby.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/standby/manifests/canonical/standby.json) |
| `skills/manifests/standby.json` | [standby/manifests/legacy_mirror/standby.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/standby/manifests/legacy_mirror/standby.json) |
| `tests/test_audio/test_echo_cancel.py` | [echo_cancellation/tests/test_audio/test_echo_cancel.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/tests/test_audio/test_echo_cancel.py) |
| `tests/test_audio/test_engine.py` | [backends/native/tests/test_audio/test_engine.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/tests/test_audio/test_engine.py) |
| `tests/test_audio/test_extension_pipeline.py` | [extensions/tests/test_audio/test_extension_pipeline.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/extensions/tests/test_audio/test_extension_pipeline.py) |
| `tests/test_audio/test_extension_playback.py` | [extensions/tests/test_audio/test_extension_playback.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/extensions/tests/test_audio/test_extension_playback.py) |
| `tests/test_audio/test_native_backend.py` | [backends/native/tests/test_audio/test_native_backend.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/tests/test_audio/test_native_backend.py) |
| `tests/test_audio/test_pipewire_backend.py` | [backends/pipewire/tests/test_audio/test_pipewire_backend.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/pipewire/tests/test_audio/test_pipewire_backend.py) |
| `tests/test_audio/test_spoken_interrupt.py` | [interruptions/tests/test_audio/test_spoken_interrupt.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/tests/test_audio/test_spoken_interrupt.py) |
| `tests/test_audio/test_standby.py` | [standby/tests/test_audio/test_standby.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/standby/tests/test_audio/test_standby.py) |
| `tests/test_audio/test_voice_lock.py` | [integrity/tests/test_audio/test_voice_lock.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/integrity/tests/test_audio/test_voice_lock.py) |
| `tests/test_core/test_agent.py` | [session/tests/test_core/test_agent.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/tests/test_core/test_agent.py) |
| `tests/test_core/test_audio_scheduler.py` | [fast_response/tests/test_core/test_audio_scheduler.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/fast_response/tests/test_core/test_audio_scheduler.py) |
| `tests/test_core/test_clean_turn_behavior.py` | [turn_detection/tests/test_core/test_clean_turn_behavior.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/turn_detection/tests/test_core/test_clean_turn_behavior.py) |
| `tests/test_core/test_connection.py` | [recovery/tests/test_core/test_connection.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/tests/test_core/test_connection.py) |
| `tests/test_core/test_greeting.py` | [greetings/tests/test_core/test_greeting.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/greetings/tests/test_core/test_greeting.py) |
| `tests/test_core/test_monitor_echo.py` | [echo_cancellation/tests/test_core/test_monitor_echo.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/tests/test_core/test_monitor_echo.py) |
| `tests/test_core/test_natural_interruption.py` | [interruptions/tests/test_core/test_natural_interruption.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/tests/test_core/test_natural_interruption.py) |
| `tests/test_core/test_parallel_voice_streaming.py` | [fast_response/tests/test_core/test_parallel_voice_streaming.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/fast_response/tests/test_core/test_parallel_voice_streaming.py) |
| `tests/test_core/test_playback_continuity.py` | [playback/tests/test_core/test_playback_continuity.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/playback/tests/test_core/test_playback_continuity.py) |
| `tests/test_core/test_response_metrics.py` | [response_latency/tests/test_core/test_response_metrics.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/response_latency/tests/test_core/test_response_metrics.py) |
| `tests/test_core/test_speech_turn_gate.py` | [turn_detection/tests/test_core/test_speech_turn_gate.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/turn_detection/tests/test_core/test_speech_turn_gate.py) |
| `tests/test_core/test_stable_echo_cancel.py` | [echo_cancellation/tests/test_core/test_stable_echo_cancel.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/tests/test_core/test_stable_echo_cancel.py) |
| `tests/test_core/test_stable_recovery.py` | [recovery/tests/test_core/test_stable_recovery.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/tests/test_core/test_stable_recovery.py) |
| `tests/test_core/test_stable_voice.py` | [session/tests/test_core/test_stable_voice.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/tests/test_core/test_stable_voice.py) |
| `tests/test_core/test_stable_voice_controls.py` | [controls/tests/test_core/test_stable_voice_controls.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/controls/tests/test_core/test_stable_voice_controls.py) |
| `tests/test_core/test_voice_reliability.py` | [recovery/tests/test_core/test_voice_reliability.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/tests/test_core/test_voice_reliability.py) |
