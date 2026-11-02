"""Compatibility shim redirecting audio.downstream to voice_layer.downstream."""
import sys
import voice_layer.downstream

sys.modules[__name__] = voice_layer.downstream
from voice_layer.downstream import *
