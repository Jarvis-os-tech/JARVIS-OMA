# voice/interruptions

SpokenInterruption and playback reference processing are complete files. Shared session and native-engine interruption methods are exact extracts. They depend on turn state, audio generations, echo references and playback queues; they are not independent functions.

## Complete original files

- [spoken_interrupt.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/spoken_interrupt.py) ← `audio/plugins/spoken_interrupt.py`

## Exact code extracts

These `.py.txt` files are verbatim source slices, not standalone implementations. Full module imports and enclosing class state remain required.

- [NativeAudioEngine.handle_barge_in](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/code_extracts/audio__engine__NativeAudioEngine__handle_barge_in.py.txt) — [audio/engine.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/engine.py:857); original lines 857–884.
- [NativeAudioEngine.trigger_barge_in](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/code_extracts/audio__engine__NativeAudioEngine__trigger_barge_in.py.txt) — [audio/engine.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/engine.py:887); original lines 887–897.
- [SpeechTurnGate.admit_interruption](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/code_extracts/core__speech_turn__SpeechTurnGate__admit_interruption.py.txt) — [core/speech_turn.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/turn_detection/speech_turn.py:72); original lines 72–76.
- [LiveVoice._accept_interruption](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/code_extracts/core__stable_voice__LiveVoice___accept_interruption.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:330); original lines 330–344.
- [LiveVoice.interrupt](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/code_extracts/core__stable_voice__LiveVoice__interrupt.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:305); original lines 305–319.
- [Playback.cancel_pending](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/code_extracts/core__stable_voice__Playback__cancel_pending.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:126); original lines 126–135.
- [Playback.interrupt](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/code_extracts/core__stable_voice__Playback__interrupt.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:160); original lines 160–162.

## Local dependencies of the containing modules

Conservative module-level list, including optional/lazy imports; not a function-level call graph.

- [audio/plugins/spoken_interrupt.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/spoken_interrupt.py) (voice)
- [core/config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/settings/config.py) (configuration)
- [core/connection.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/connection.py) (voice)
- [core/harness_config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/prompts/harness_config.py) (configuration)
- [core/ipc.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/ipc.py) (runtime)
- [core/monitor_echo.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/monitor_echo.py) (voice)
- [core/secret_env.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/secret_env.py) (configuration)
- [core/speech_turn.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/turn_detection/speech_turn.py) (voice)
- [core/stable_capabilities.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/capability_services/stable_capabilities.py) (runtime)
- [core/stable_recovery.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/stable_recovery.py) (voice)
- [skills/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/package_markers/skills/__init__.py) (skill_registry)
