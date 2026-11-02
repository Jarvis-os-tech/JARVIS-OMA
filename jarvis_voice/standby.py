"""Compatibility shim redirecting jarvis_voice.standby to voice_layer.standby."""
import sys
import voice_layer.standby

sys.modules[__name__] = voice_layer.standby
from voice_layer.standby import *
