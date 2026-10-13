"""Core feature package: voice agent runtime & configuration."""
from core.config import Config, load_config


def __getattr__(name: str):
    if name in ('LiveVoice', 'main'):
        from core.agent import LiveVoice, main
        return LiveVoice if name == 'LiveVoice' else main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ['Config', 'load_config', 'LiveVoice', 'main']
