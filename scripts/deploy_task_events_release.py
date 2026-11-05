"""Activate a certified task release and back up the user widget plugin."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from scripts.prepare_system_integration_release import status
from scripts.prepare_parsing_release import restore_settings
from orchestration.release_manager import ReleaseManager

def deploy(staged):
    runtime = Path.home() / '.local/share/jarvis-runtime'
    metadata = json.loads((staged / 'release.json').read_text())['task_events']
    parent = Path(metadata['parent'])
    if (runtime / 'current').resolve() != parent:
        raise RuntimeError('Current release changed')
    for relative, expected in metadata['sha256'].items():
        if hashlib.sha256((staged / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Candidate changed: ' + relative)
    before = status()
    if not before or before.get('tools_in_flight') or before.get('vision_mode', 'off') != 'off':
        raise RuntimeError('Tools or vision active, or status unknown')
    plugin = Path.home() / '.config/omarchy/plugins/jarvis.widgets'
    if plugin.is_symlink() or not plugin.is_dir():
        raise RuntimeError('Expected existing user widget plugin')
    initial_canvas = json.loads(subprocess.run(['omarchy-shell', 'jarvis-canvas', 'status'],
        check=True, timeout=5, capture_output=True, text=True).stdout)
    if initial_canvas.get('widgets') or initial_canvas.get('inputVisible'):
        raise RuntimeError('Existing user widgets or input need preserving; restart deferred')
    backup = Path.home() / '.config/omarchy/backups' / ('task-events-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    shutil.copytree(plugin, backup)
    manager = ReleaseManager(runtime)
    installed = None
    try:
        for path in (staged / 'ui/jarvis_widgets').iterdir():
            if path.is_file() and path.suffix in {'.qml', '.js', '.json', '.py'}:
                shutil.copy2(path, plugin / path.name)
        subprocess.run(['omarchy-shell', 'shell', 'rescanPlugins'], check=True, timeout=5, capture_output=True)
        subprocess.run(['omarchy', 'restart', 'shell'], check=True, timeout=15, capture_output=True)
        deadline = time.monotonic() + 20
        canvas = {}
        while time.monotonic() < deadline:
            probe = subprocess.run(['omarchy-shell', 'jarvis-canvas', 'status'], timeout=3, capture_output=True, text=True)
            try:
                canvas = json.loads(probe.stdout)
            except ValueError:
                pass
            if 'taskCursor' in canvas:
                break
            time.sleep(.5)
        if 'task_cursor' not in canvas and 'taskCursor' not in canvas:
            raise RuntimeError('New task handler was not loaded: ' + str(canvas))
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-task-events'
        installed = manager.install_prepared_release(staged, name, expected_current=parent,
                            expected_hashes=metadata['sha256'], timeout=25)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            ready = status()
            audio_ready = (not before.get('microphone', {}).get('muted') or
                           ready.get('microphone', {}).get('source', '').startswith('jarvis_aec_'))
            connection_ready = before.get('standby') or before.get('muted') or ready.get('connected')
            if audio_ready and connection_ready:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('Voice or audio did not become ready')
        restore_settings(before)
        after = status()
        if not after.get('control_enabled'):
            raise RuntimeError('Control did not restart')
    except Exception:
        if installed is not None:
            manager._switch_release(parent, 25, expected_current=installed)
            restore_settings(before)
        shutil.rmtree(plugin)
        shutil.copytree(backup, plugin)
        subprocess.run(['omarchy-shell', 'shell', 'rescanPlugins'], timeout=5, capture_output=True)
        subprocess.run(['omarchy', 'restart', 'shell'], timeout=15, capture_output=True)
        raise
    report = dict(installed=str(installed), previous=str(parent), plugin_backup=str(backup),
                  tests=metadata['tests'], status=after, canvas=canvas)
    Path('/tmp/jarvis-task-events-deployment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))

if __name__ == '__main__':
    deploy(Path(sys.argv[1]).resolve(strict=True))
