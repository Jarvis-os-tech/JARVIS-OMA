"""Compatibility shim redirecting jarvis_voice.background to voice_layer.background."""
import sys
import voice_layer.background

sys.modules[__name__] = voice_layer.background
from voice_layer.background import *
