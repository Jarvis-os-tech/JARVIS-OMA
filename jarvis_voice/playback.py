"""Compatibility shim redirecting jarvis_voice.playback to voice_layer.playback."""
import sys
import voice_layer.playback

sys.modules[__name__] = voice_layer.playback
from voice_layer.playback import *
