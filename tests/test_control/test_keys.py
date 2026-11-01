"""Tests for key translation and keysym normalization."""
import pytest
from jarvis_control.keys import normalise_key, normalise_mods


def test_enter_becomes_return():
    key, err = normalise_key("enter")
    assert key == "Return"
    assert err is None


def test_abbreviations_translate_to_xkb_keysyms():
    key, err = normalise_key("esc")
    assert key == "Escape"
    assert err is None


def test_modifier_normalization():
    mods, err = normalise_mods("SUPER")
    assert mods == "SUPER"
    assert err is None
    mods, err = normalise_mods("CTRL+ALT")
    assert mods == "CTRL ALT"
    assert err is None
