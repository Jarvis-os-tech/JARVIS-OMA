"""The Voice Layer — sovereign voice foundation for JARVIS OS.

Unified package providing real-time audio capture, PipeWire AEC, Silero VAD,
bounded playback with generation fences, offline wake-word standby, and
full-duplex Gemini Live conversation sessions.
"""
from .daemon import LiveVoice, live_config
from .echo import EchoCancellation, MonitorEchoCancellation, monitor_properties
from .speech import SpeechTurnGate, SileroSpeechDetector, SpokenInterruption, GateFrame
from .playback import Playback, MicrophoneBacklogError, PlaybackBacklogError
from .recovery import ConnectionRecovery, RecoveryDecision
from .standby import OpenWakeWordDetector, StandbyController, WakeWordUnavailable
from .ipc import ControlServer
from .config import Config, load as load_config, load_env

__version__ = '0.1.0'

__all__ = [
    'LiveVoice',
    'live_config',
    'EchoCancellation',
    'MonitorEchoCancellation',
    'monitor_properties',
    'SpeechTurnGate',
    'SileroSpeechDetector',
    'SpokenInterruption',
    'GateFrame',
    'Playback',
    'MicrophoneBacklogError',
    'PlaybackBacklogError',
    'ConnectionRecovery',
    'RecoveryDecision',
    'OpenWakeWordDetector',
    'StandbyController',
    'WakeWordUnavailable',
    'ControlServer',
    'Config',
    'load_config',
    'load_env',
]
