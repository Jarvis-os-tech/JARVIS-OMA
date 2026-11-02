"""Compatibility shim redirecting jarvis_voice to voice_layer."""
import sys
import voice_layer

sys.modules[__name__] = voice_layer
from voice_layer import *
from voice_layer import __version__
