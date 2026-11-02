import pytest

from jarvis_control.wayland_keyboard import keymap_for_shortcut


@pytest.mark.parametrize('key,code', [('Return', 28), ('Escape', 1), ('Tab', 15), ('BackSpace', 14)])
def test_shortcuts_keep_real_physical_keycodes(key, code):
    data, actual, mask = keymap_for_shortcut('', key)
    assert data.startswith(b'xkb_keymap') and data.endswith(b'\0')
    assert actual == code
    assert mask == 0


def test_control_chords_do_not_add_shift_for_an_uppercase_letter_name():
    _, code, mask = keymap_for_shortcut('CTRL', 'A')
    assert code == 30 and mask == 4


def test_unknown_keys_or_modifiers_are_rejected_before_connecting():
    with pytest.raises(ValueError):
        keymap_for_shortcut('ARBITRARY', 'Return')
    with pytest.raises(ValueError):
        keymap_for_shortcut('', 'not-a-key')
