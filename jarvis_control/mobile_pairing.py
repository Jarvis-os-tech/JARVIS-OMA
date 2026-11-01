"""Open a private phone-pairing QR using the PC's existing credential loader."""
from pathlib import Path
import subprocess
import sys

SCHEMA = {
    'name': 'phone_pair',
    'description': 'Open the private JARVIS Mobile pairing QR code on this PC ONLY when the user explicitly commands to pair a phone, scan a QR code, or open the pairing window (e.g. "open pairing QR", "pair my phone"). Do NOT invoke when the user is reporting connection status or discussing issues.',
    'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
}


def open_pairing_qr():
    root = Path(__file__).resolve().parents[1]
    from scripts.pairing_window_state import create, path_for
    session = create()
    destination = path_for(session).with_suffix('.png')
    result = subprocess.run([sys.executable, str(root / 'scripts/jarvis_pair.py'),
        '--output', str(destination), '--no-ascii', '--transient', '--pairing-session', session], cwd=root,
        capture_output=True, text=True, timeout=30)
    if result.returncode or not destination.exists():
        path_for(session).unlink(missing_ok=True)
        raise RuntimeError('Unable to create the phone pairing QR. Check desktop Gemini configuration and QR image support.')
    subprocess.Popen(['/usr/bin/python', str(root / 'scripts/mobile_pairing_widget.py'),
        '--image', str(destination), '--session', session], cwd=root,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return 'Opened the private JARVIS pairing widget. Scan it from your phone. The window closes after the phone confirms connection. It expires after five minutes.'
