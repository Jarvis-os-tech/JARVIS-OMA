"""Compatibility shim redirecting jarvis_voice.recovery to voice_layer.recovery."""
import sys
import voice_layer.recovery

sys.modules[__name__] = voice_layer.recovery
from voice_layer.recovery import *
