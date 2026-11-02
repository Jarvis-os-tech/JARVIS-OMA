"""Compatibility shim redirecting jarvis_voice.microphone to voice_layer.microphone."""
import sys
import voice_layer.microphone

sys.modules[__name__] = voice_layer.microphone
from voice_layer.microphone import *
