import pytest

from jarvis_control.wayland_keyboard import keymap_for_shortcut, literal_plan


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


def test_literal_typing_keeps_case_and_uses_printable_physical_codes():
    _, plan=literal_plan('Aa!')
    assert plan==[(30,1),(30,0),(2,1)]
    _, plan=literal_plan('JARVIS proof - Replacement 0123456789')
    assert all(code not in (1,14,15,28) for code,_ in plan)


def test_multiline_text_requires_paste_instead_of_submitting_enter():
    with pytest.raises(ValueError,match='Unsupported literal text'):
        literal_plan('first\nsecond')
