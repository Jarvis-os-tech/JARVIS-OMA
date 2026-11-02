"""Compatibility shim redirecting jarvis_voice.config to voice_layer.config."""
import sys
import voice_layer.config

sys.modules[__name__] = voice_layer.config
from voice_layer.config import *
