import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from scripts.jarvis_mode import switch_mode, current_mode, get_test_root, get_production_root

def test_get_roots():
    test_root = get_test_root()
    assert (test_root / "jarvis_voice").is_dir()
    prod_root = get_production_root()
    assert "jarvis-runtime" in str(prod_root)

def test_switch_mode_test(tmp_path):
    with patch("scripts.jarvis_mode.DROPIN_DIR", tmp_path / "dropin"):
        with patch("scripts.jarvis_mode.DROPIN", tmp_path / "dropin" / "mode.conf"):
            with patch("scripts.jarvis_mode.BRIDGE_DROPIN_DIR", tmp_path / "bridge_dropin"):
                with patch("scripts.jarvis_mode.BRIDGE_DROPIN", tmp_path / "bridge_dropin" / "mode.conf"):
                    with patch("scripts.jarvis_mode.restart_services", return_value=True):
                        with patch("scripts.jarvis_mode._update_symlinks"):
                            res = switch_mode("test", restart=False)
                            assert res["status"] == "success"
                            assert res["mode"] == "test"
                            assert (tmp_path / "dropin" / "mode.conf").exists()
                            content = (tmp_path / "dropin" / "mode.conf").read_text()
                            assert "JARVIS OS" in content or "bin/jarvis-voice" in content

def test_switch_mode_production(tmp_path):
    dropin = tmp_path / "dropin" / "mode.conf"
    dropin.parent.mkdir(parents=True)
    dropin.write_text("[Service]\n")
    with patch("scripts.jarvis_mode.DROPIN_DIR", tmp_path / "dropin"):
        with patch("scripts.jarvis_mode.DROPIN", dropin):
            with patch("scripts.jarvis_mode.BRIDGE_DROPIN_DIR", tmp_path / "bridge_dropin"):
                with patch("scripts.jarvis_mode.BRIDGE_DROPIN", tmp_path / "bridge_dropin" / "mode.conf"):
                    with patch("scripts.jarvis_mode.restart_services", return_value=True):
                        with patch("scripts.jarvis_mode._update_symlinks"):
                            res = switch_mode("production", restart=False)
                            assert res["status"] == "success"
                            assert res["mode"] == "production"
                            assert not dropin.exists()
