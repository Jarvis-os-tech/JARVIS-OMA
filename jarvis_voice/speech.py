"""Compatibility shim redirecting jarvis_voice.speech to voice_layer.speech."""
import sys
import voice_layer.speech

sys.modules[__name__] = voice_layer.speech
from voice_layer.speech import *
