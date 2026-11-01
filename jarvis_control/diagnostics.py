"""Read-only readiness checks for the actual JARVIS configuration."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil


def report(voice, control):
    checks = {}

    def check(name, ok, detail):
        checks[name] = {'ok': bool(ok), 'detail': detail}

    for executable in ('pw-record', 'pw-play', 'pactl', 'hyprctl', 'omarchy'):
        check(executable, shutil.which(executable), executable)
    for module in ('numpy', 'onnxruntime', 'google.genai'):
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError):
            found = False
        check(module, found, 'Python dependency')
    if voice.standby.enabled:
        check('openwakeword', importlib.util.find_spec('openwakeword') is not None,
              'Offline Hey Jarvis wake-word runtime')
    check('voice credential', os.environ.get(voice.api_key_env), voice.api_key_env)
    if control.tasks_enabled:
        for executable in ('bwrap', 'systemd-run'):
            check(f'tasks: {executable}', shutil.which(executable), executable)
        if control.tasks_provider == 'codex':
            check('tasks: codex', shutil.which('codex'), 'Codex CLI')
        else:
            check('task credential', os.environ.get(control.api_key_env), control.api_key_env)
    if control.vision_enabled:
        from .vision import settings
        camera = settings(control)
        for executable in ('ffmpeg', 'ffplay'):
            check(f'vision: {executable}', shutil.which(executable), executable)
        check('camera device', Path(camera['device']).exists(), camera['device'])
        if camera['api_key_env']:
            check('vision credential', os.environ.get(camera['api_key_env']), camera['api_key_env'])
    return {'ok': all(item['ok'] for item in checks.values()), 'checks': checks,
            'tasks_enabled': control.tasks_enabled, 'vision_enabled': control.vision_enabled}
