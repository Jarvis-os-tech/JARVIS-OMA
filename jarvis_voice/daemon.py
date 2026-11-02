"""Compatibility shim redirecting jarvis_voice.daemon to voice_layer.daemon."""
import sys
import voice_layer.daemon

sys.modules[__name__] = voice_layer.daemon
from voice_layer.daemon import *
