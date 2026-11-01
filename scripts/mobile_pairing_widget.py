#!/usr/bin/python
"""A dedicated QR widget. Only its own confirmed pairing session closes it."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio
from pairing_window_state import status, path_for


def place_pip():
    """Position only this process's window; no permanent desktop config changes."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True
    try:
        clients = json.loads(subprocess.check_output(['hyprctl', '-j', 'clients'], timeout=2))
        client = next((c for c in clients if c.get('pid') == os.getpid()), None)
        if not client or not re.fullmatch(r'0x[a-fA-F0-9]+', client.get('address', '')):
            return False
        monitors = json.loads(subprocess.check_output(['hyprctl', '-j', 'monitors'], timeout=2))
        monitor = next((m for m in monitors if m.get('focused')), monitors[0])
        scale = monitor.get('scale', 1) or 1
        x = max(monitor['x'] + 16, int(monitor['x'] + monitor['width'] / scale - 320))
        y = max(monitor['y'] + 48, int(monitor['y'] + monitor['height'] / scale - 408))
        selector = 'address:' + client['address']
        if not client.get('floating'):
            subprocess.run(['hyprctl', 'eval',
                f"hl.dispatch(hl.dsp.window.float({{window='{selector}',action='set'}}))"],
                capture_output=True, text=True, timeout=2)
            return False  # The compositor applies floating before pinning is allowed.
        if client.get('size') != [304, 384]:
            action = f"hl.dsp.window.resize({{window='{selector}',x=304,y=384,relative=false}})"
        elif any(abs(a - b) > 2 for a, b in zip(client.get('at', [0, 0]), [x, y])):
            action = f"hl.dsp.window.move({{window='{selector}',x={x},y={y},relative=false}})"
        elif not client.get("pinned"):
            action = f"hl.dsp.window.pin({{window='{selector}',action='set'}})"
        else:
            return True
        subprocess.run(['hyprctl', 'eval', 'hl.dispatch(' + action + ')'],
            capture_output=True, text=True, timeout=2)
        return False  # Apply each stage after the compositor confirms the previous one.

    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--session', required=True)
    args = parser.parse_args()
    # Validate session and image location before starting the window.
    state = path_for(args.session)
    if not args.image.is_file() or not state.is_file():
        raise SystemExit('Pairing image/session unavailable')
    app = Gtk.Application(application_id='org.jarvis.MobilePairing', flags=Gio.ApplicationFlags.NON_UNIQUE)

    def activate(application):
        window = Gtk.ApplicationWindow(application=application, title='JARVIS · Pair your phone')
        window.set_default_size(304, 384)
        window.set_resizable(False)
        header = Gtk.HeaderBar()
        header.set_decoration_layout(":close")
        header.set_title_widget(Gtk.Label(label="JARVIS · Pair phone"))
        window.set_titlebar(header)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(box, 'set_margin_' + side)(12)
        picture = Gtk.Picture.new_for_filename(str(args.image))
        picture.set_size_request(260, 260)
        picture.set_can_shrink(True)
        box.append(picture)
        message = Gtk.Label(label='Scan with JARVIS Mobile')
        message.set_wrap(True)
        box.append(message)
        hint = Gtk.Label(label='Closes when connected · 5 min expiry')
        hint.set_wrap(True)
        hint.add_css_class('dim-label')
        box.append(hint)
        window.set_child(box)

        def poll():
            try:
                current = status(args.session)
            except (OSError, ValueError):
                current = 'expired'
            if current != 'pending':
                window.close()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        GLib.timeout_add(500, poll)
        window.present()
        attempts = [0]
        def position():
            attempts[0] += 1
            return not place_pip() and attempts[0] < 40
        GLib.timeout_add(250, position)

    app.connect('activate', activate)
    try:
        app.run([])
    finally:
        args.image.unlink(missing_ok=True)
        state.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
