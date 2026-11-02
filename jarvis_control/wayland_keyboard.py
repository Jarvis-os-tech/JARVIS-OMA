"""Deliver one foreground shortcut with a complete, conventional XKB keymap.

Some clients resolve bindings by keycode as well as keysym. The small temporary
maps used by text injectors can therefore deliver Return without activating an
entry. This helper runs in a bounded child process and uses physical keycodes.
It requires only the Wayland and XKB libraries already used by the desktop.
"""
from __future__ import annotations

import ctypes as c
import sys
import tempfile
import time


class Interface(c.Structure):
    pass


class Message(c.Structure):
    _fields_ = [('name', c.c_char_p), ('signature', c.c_char_p),
                ('types', c.POINTER(c.POINTER(Interface)))]


Interface._fields_ = [('name', c.c_char_p), ('version', c.c_int),
                     ('method_count', c.c_int), ('methods', c.POINTER(Message)),
                     ('event_count', c.c_int), ('events', c.POINTER(Message))]


def _function(lib, name, restype, *argtypes):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = restype, list(argtypes)
    return fn


def keymap_for_shortcut(mods, keysym):
    """Return a full US map, evdev code and modifier mask; never inject text."""
    xkb = c.CDLL('libxkbcommon.so.0')
    ptr, uint = c.c_void_p, c.c_uint
    context_new = _function(xkb, 'xkb_context_new', ptr, c.c_int)
    map_new = _function(xkb, 'xkb_keymap_new_from_names', ptr, ptr, ptr, c.c_int)
    as_string = _function(xkb, 'xkb_keymap_get_as_string', ptr, ptr, c.c_int)
    from_name = _function(xkb, 'xkb_keysym_from_name', uint, c.c_char_p, c.c_int)
    symbols = _function(xkb, 'xkb_keymap_key_get_syms_by_level', c.c_int,
                        ptr, uint, uint, uint, c.POINTER(c.POINTER(uint)))
    mod_index = _function(xkb, 'xkb_keymap_mod_get_index', uint, ptr, c.c_char_p)
    minimum = _function(xkb, 'xkb_keymap_min_keycode', uint, ptr)
    maximum = _function(xkb, 'xkb_keymap_max_keycode', uint, ptr)
    context_unref = _function(xkb, 'xkb_context_unref', None, ptr)
    map_unref = _function(xkb, 'xkb_keymap_unref', None, ptr)
    libc = c.CDLL(None)
    free = _function(libc, 'free', None, ptr)

    class Names(c.Structure):
        _fields_ = [(name, c.c_char_p) for name in
                    ('rules', 'model', 'layout', 'variant', 'options')]

    context = context_new(0)
    keymap = None
    try:
        if not context:
            raise RuntimeError('Could not create keyboard context')
        names = Names(b'evdev', b'pc105', b'us', b'', b'')
        keymap = map_new(context, c.byref(names), 0)
        wanted = from_name(keysym.encode(), 1)
        if not keymap or not wanted:
            raise ValueError('Invalid keyboard map or keysym')
        aliases = {'CTRL': 'Control', 'SHIFT': 'Shift', 'ALT': 'Mod1', 'SUPER': 'Mod4'}
        mask = 0
        for mod in mods.split():
            if mod not in aliases:
                raise ValueError('Unsupported shortcut modifier')
            index = mod_index(keymap, aliases[mod].encode())
            if index >= 32:
                raise ValueError('Modifier is missing from keyboard map')
            mask |= 1 << index
        # Prefer unshifted keys; named keys such as Return retain evdev 28.
        for level in (0, 1):
            for code in range(minimum(keymap), maximum(keymap) + 1):
                values = c.POINTER(uint)()
                count = symbols(keymap, code, 0, level, c.byref(values))
                if not any(values[i] == wanted for i in range(count)):
                    continue
                text = as_string(keymap, 1)
                if not text:
                    raise RuntimeError('Could not serialize keyboard map')
                try:
                    data = c.string_at(text) + b'\0'
                finally:
                    free(text)
                if level:
                    mask |= 1 << mod_index(keymap, b'Shift')
                return data, code - 8, mask
        raise ValueError('Keysym is not available in the shortcut keyboard map')
    finally:
        if keymap:
            map_unref(keymap)
        if context:
            context_unref(context)


def send_shortcut(mods, keysym):
    data, keycode, mask = keymap_for_shortcut(mods, keysym)
    wl = c.CDLL('libwayland-client.so.0')
    ptr, uint = c.c_void_p, c.c_uint
    connect = _function(wl, 'wl_display_connect', ptr, c.c_char_p)
    disconnect = _function(wl, 'wl_display_disconnect', None, ptr)
    roundtrip = _function(wl, 'wl_display_roundtrip', c.c_int, ptr)
    marshal = _function(wl, 'wl_proxy_marshal_flags', ptr, ptr, uint,
                        c.POINTER(Interface), uint, uint)
    listen = _function(wl, 'wl_proxy_add_listener', c.c_int, ptr, ptr, ptr)
    registry_i = Interface.in_dll(wl, 'wl_registry_interface')
    seat_i = Interface.in_dll(wl, 'wl_seat_interface')
    requests = (Message * 4)(Message(b'keymap', b'uhu', None),
                            Message(b'key', b'uuu', None),
                            Message(b'modifiers', b'uuuu', None),
                            Message(b'destroy', b'', None))
    keyboard_i = Interface(b'zwp_virtual_keyboard_v1', 1, 4, requests, 0, None)
    types = (c.POINTER(Interface) * 2)(c.pointer(seat_i), c.pointer(keyboard_i))
    create = (Message * 1)(Message(b'create_virtual_keyboard', b'on', types))
    manager_i = Interface(b'zwp_virtual_keyboard_manager_v1', 1, 1, create, 0, None)
    objects = {}
    global_cb = c.CFUNCTYPE(None, ptr, ptr, uint, c.c_char_p, uint)
    remove_cb = c.CFUNCTYPE(None, ptr, ptr, uint)

    @global_cb
    def found(_, registry, name, interface, version):
        target = seat_i if interface == b'wl_seat' else manager_i if interface == manager_i.name else None
        if target is not None and interface not in objects:
            objects[interface] = marshal(registry, 0, c.byref(target), 1, 0,
                                         uint(name), target.name, uint(1), ptr())

    @remove_cb
    def removed(*_):
        pass

    callbacks = (ptr * 2)(c.cast(found, ptr), c.cast(removed, ptr))
    display = connect(None)
    keyboard = None
    if not display:
        raise RuntimeError('Wayland connection failed')
    try:
        registry = marshal(display, 1, c.byref(registry_i), 1, 0, ptr())
        if listen(registry, callbacks, None) != 0 or roundtrip(display) < 0:
            raise RuntimeError('Could not read Wayland registry')
        seat, manager = objects.get(b'wl_seat'), objects.get(manager_i.name)
        if not seat or not manager:
            raise RuntimeError('Desktop does not provide a virtual keyboard')
        keyboard = marshal(manager, 0, c.byref(keyboard_i), 1, 0, ptr(seat), ptr())
        if not keyboard:
            raise RuntimeError('Virtual keyboard creation failed')
        with tempfile.TemporaryFile() as stream:
            stream.write(data)
            stream.flush()
            marshal(keyboard, 0, None, 1, 0, uint(1), c.c_int(stream.fileno()), uint(len(data)))
            marshal(keyboard, 2, None, 1, 0, uint(mask), uint(0), uint(0), uint(0))
            if roundtrip(display) < 0:
                raise RuntimeError('Keyboard map was rejected')
            for state in (1, 0):
                marshal(keyboard, 1, None, 1, 0, uint(int(time.monotonic()*1000) & 0xffffffff),
                        uint(keycode), uint(state))
                if roundtrip(display) < 0:
                    raise RuntimeError('Keyboard connection lost during delivery')
                time.sleep(.02)
            marshal(keyboard, 2, None, 1, 0, uint(0), uint(0), uint(0), uint(0))
            roundtrip(display)
            time.sleep(.03)
    finally:
        if keyboard:
            marshal(keyboard, 3, None, 1, 1)
            roundtrip(display)
        disconnect(display)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3:
            raise ValueError('Expected modifiers and a keysym')
        send_shortcut(sys.argv[1], sys.argv[2])
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
