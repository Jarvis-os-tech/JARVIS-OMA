"""Compatibility shim redirecting echo_cancel to voice_layer.echo."""
import sys
import voice_layer.echo

sys.modules[__name__] = voice_layer.echo
