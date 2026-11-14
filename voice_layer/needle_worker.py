"""Isolated, offline-only Needle inference. Never executes model-selected tools."""
import copy
import base64
import json
import os
import re
from pathlib import Path
import sys
import time

import needle


def main():
    root = Path(os.environ['JARVIS_NEEDLE_HOME'])
    # Every artifact is provisioned at install time; runtime never calls fetch.
    needle._base_weights_path = lambda generation: str(root / 'needle3.cact')
    needle._library_path = lambda generation=3: str(root / 'libneedle.so')
    # The worker cannot connect to the network, even if an upstream helper tries.
    import socket
    def offline(*args, **kwargs):
        raise OSError('Network access disabled in the offline worker')
    socket.socket.connect = offline
    socket.socket.connect_ex = offline
    socket.create_connection = offline
    from offline_speech import OfflineSpeech
    speech = OfflineSpeech()
    config = json.loads(sys.stdin.buffer.readline())
    # Load the model once, but keep each command's tool prompt small.
    needle._lib(3)
    needle._load_base(needle._lib(3), 3)
    models = {}
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin.buffer:
        request = json.loads(line)
        if 'speak' in request:
            print(json.dumps({'pcm': ''}), flush=True)
            continue
        text = request.get('text')
        if not isinstance(text, str) or len(text) > 240:
            raise ValueError('Invalid command text')
        started = time.monotonic()
        lowered = text.casefold()
        if re.search(r'\b(volume|sound|audio|speaker|speakers|louder|quieter|softer)\b', lowered):
            if re.search(r'\d|\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\b', lowered):
                names = ('set_volume',)
            elif re.search(r'\b(quieter|softer|decrease|lower|down)\b', lowered):
                names = ('decrease_volume',)
            elif re.search(r'\b(louder|increase|raise|up)\b', lowered):
                names = ('increase_volume',)
            else:
                names = ()
        elif re.search(r'\b(brightness|screen|display|brighter|dimmer)\b', lowered):
            if re.search(r'\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\b', lowered):
                names = ('set_brightness',)
            elif re.search(r'\b(dimmer|decrease|lower|down)\b', lowered):
                names = ('decrease_brightness',)
            elif re.search(r'\b(brighter|increase|raise|up)\b', lowered):
                names = ('increase_brightness',)
            else:
                names = ()
        elif 'workspace' in lowered:
            names = ('switch_workspace',)
        elif re.search(r'\b(open|launch|start)\b', lowered):
            names = ('open_application',)
        else:
            print(json.dumps({'confidence': 0, 'function_calls': [], 'elapsed_ms': 0}), flush=True)
            continue
        selected = [copy.deepcopy(tool) for tool in config['tools'] if tool['name'] in names]
        if names == ('open_application',):
            candidates = request.get('app_candidates', [])
            if not selected or not candidates:
                print(json.dumps({'confidence': 0, 'function_calls': [], 'elapsed_ms': 0}), flush=True)
                continue
            allowed = selected[0]['parameters']['properties']['app']['enum']
            selected[0]['parameters']['properties']['app']['enum'] = [app for app in allowed if app in candidates]
        if not selected:
            print(json.dumps({'confidence': 0, 'function_calls': [], 'elapsed_ms': 0}), flush=True)
            continue
        key = json.dumps(selected, sort_keys=True)
        if key not in models:
            if len(models) >= 16:
                old_key = next(iter(models))
                models.pop(old_key).close()
            models[key] = needle.Needle(tools=selected, generation=3, stateless=True, auto_date=False)
        result = models[key].complete(text, max_new_tokens=48)
        result['elapsed_ms'] = round((time.monotonic()-started)*1000)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
