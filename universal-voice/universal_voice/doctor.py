"""Read-only preflight: never starts capture, a service or a cloud session."""
import importlib
import os
from pathlib import Path
import platform
import shutil
import sys


def check():
    errors = []
    if platform.system() != 'Linux':
        errors.append('This build requires Linux with PipeWire')
    for command in ('pw-record', 'pw-play', 'pw-cli', 'pactl'):
        if not shutil.which(command):
            errors.append('Missing audio command: ' + command)
    for module in ('numpy', 'onnxruntime', 'openwakeword', 'google.genai', 'jsonschema'):
        try:
            importlib.import_module(module)
        except (ImportError, OSError) as error:
            errors.append(f'{module}: {error}')
    try:
        from .config import load
        config = load()
        from .speech import SileroSpeechDetector
        SileroSpeechDetector()
        print(f'Config and local VAD ready (model={config.model})')
    except Exception as error:
        errors.append(f'Configuration/VAD: {error}')
    if not os.getenv('XDG_RUNTIME_DIR'):
        print('NOTE: no desktop session runtime; a working user PipeWire session is required')
    for error in errors:
        print('FAIL: ' + error, file=sys.stderr)
    if errors:
        return 1
    print('PASS: local dependencies ready. Microphone, speakers and cloud access are not tested.')
    return 0
