"""Compatibility shim redirecting jarvis_voice.ipc to voice_layer.ipc."""
import sys
import voice_layer.ipc

sys.modules[__name__] = voice_layer.ipc
from voice_layer.ipc import *
