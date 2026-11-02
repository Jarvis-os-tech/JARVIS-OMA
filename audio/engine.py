"""Compatibility shim redirecting audio.engine to voice_layer.engine."""
import sys
import voice_layer.engine

sys.modules[__name__] = voice_layer.engine
from voice_layer.engine import *
