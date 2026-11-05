"""Open a private phone-pairing QR using the PC's existing credential loader."""
from pathlib import Path
import json
import subprocess
import sys
import threading
import time

SCHEMA = {
    'name': 'phone_pair',
    'description': 'Open the private JARVIS Mobile pairing QR code on this PC ONLY when the user explicitly commands to pair a phone, scan a QR code, or open the pairing window (e.g. "open pairing QR", "pair my phone"). Do NOT invoke when the user is reporting connection status or discussing issues.',
    'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
}


def open_pairing_qr():
    root = Path(__file__).resolve().parents[1]
    from scripts.pairing_window_state import create, path_for, status
    from ui.jarvis_widgets import backend

    session = create()
    destination = path_for(session).with_suffix('.png')
    result = subprocess.run([sys.executable, str(root / 'scripts/jarvis_pair.py'),
        '--output', str(destination), '--no-ascii', '--transient', '--pairing-session', session], cwd=root,
        capture_output=True, text=True, timeout=30)
    if result.returncode or not destination.exists():
        path_for(session).unlink(missing_ok=True)
        raise RuntimeError('Unable to create the phone pairing QR. Check desktop Gemini configuration and QR image support.')

    creds_file = Path.home() / ".config/jarvis/pairing_credentials.json"
    if creds_file.is_file():
        try:
            with open(creds_file) as f:
                creds = json.load(f)
            payload = {
                'v': 1, 'pid': creds['project_id'], 'dev': creds['device_id'],
                'tok': creds['auth_token'], 'bkt': creds['gcs_bucket'],
                'ep': creds['endpoint'], 'exec': 'http://127.0.0.1:8766', 'key': ''
            }
            content = json.dumps(payload, separators=(',', ':'))
        except Exception:
            content = session
    else:
        content = session

    widget = backend.make_widget(
        "qr", "📱 Scan to Pair JARVIS Mobile",
        {"content": content},
        widget_id="jarvis-pairing-qr", presentation="floating", expires_seconds=300
    )
    backend.shell_call("present", widget)

    def _auto_dismiss():
        for _ in range(300):
            time.sleep(1)
            try:
                if status(session) != 'pending':
                    break
            except Exception:
                break
        try:
            backend.shell_call("manage", {"id": "jarvis-pairing-qr", "action": "dismiss"})
        except Exception:
            pass

    thread = threading.Thread(target=_auto_dismiss, daemon=True)
    thread.start()

    return 'Opened the private JARVIS pairing widget. Scan it from your phone. The card closes after the phone confirms connection or in 5 minutes.'
