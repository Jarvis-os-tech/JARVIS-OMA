"""Compatibility shim redirecting audio.extension to voice_layer.extension."""
import sys
import voice_layer.extension

sys.modules[__name__] = voice_layer.extension
from voice_layer.extension import *
