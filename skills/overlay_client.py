#!/usr/bin/env python3
"""Native Wayland transparent floating overlay client for JARVIS Input Bar."""
import os
import signal
import sys

try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('WebKit2', '4.1')
    from gi.repository import Gtk, WebKit2, Gdk, GLib
except Exception as err:
    print(f"WebKitGTK not available: {err}", file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: overlay_client.py <url>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]

    # Application ID for Hyprland window rules
    GLib.set_prgname("JarvisInputBar")

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("JARVIS Input Bar")
    win.set_role("JarvisInputBar")
    win.set_decorated(False)
    win.set_app_paintable(True)
    win.set_resizable(False)
    win.set_keep_above(True)

    # Set exact compact dimensions: width 600, height 50
    win.set_default_size(600, 50)
    win.set_size_request(600, 50)

    # Enable native RGBA visual for true Wayland compositor transparency
    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual:
        win.set_visual(visual)

    # Ephemeral context to avoid cache pollution
    ctx = WebKit2.WebContext.new_ephemeral()
    webview = WebKit2.WebView.new_with_context(ctx)
    webview.set_size_request(600, 50)
    webview.set_background_color(Gdk.RGBA(0.0, 0.0, 0.0, 0.0))

    settings = webview.get_settings()
    settings.set_enable_webgl(False)
    settings.set_enable_webaudio(False)
    settings.set_enable_media_stream(False)
    settings.set_enable_smooth_scrolling(True)
    settings.set_javascript_can_open_windows_automatically(False)

    # Handle window.close() from JavaScript
    webview.connect("close", lambda w: Gtk.main_quit())

    webview.load_uri(url)
    win.add(webview)
    win.connect("destroy", Gtk.main_quit)

    signal.signal(signal.SIGINT, lambda s, f: Gtk.main_quit())
    signal.signal(signal.SIGTERM, lambda s, f: Gtk.main_quit())

    win.show_all()
    win.present()
    Gtk.main()


if __name__ == "__main__":
    main()
