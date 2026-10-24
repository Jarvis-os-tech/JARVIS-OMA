"""Static and IPC contract tests for the JARVIS Aura Orbit."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ORBIT = ROOT / "ui" / "omarchy-ai.orbit"


def test_aura_orbit_manifest_and_sources():
    manifest = json.loads((ORBIT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["id"] == "omarchy-ai.orbit"
    assert manifest["entryPoints"]["panel"] == "OrbitOverlay.qml"
    assert (ORBIT / "AuraFieldOrbit.qml").exists()


def test_overlay_is_small_click_through_and_state_driven():
    content = (ORBIT / "OrbitOverlay.qml").read_text(encoding="utf-8")
    assert "WlrLayer.Overlay" in content
    assert "Region { item: orbitWidget }" in content
    assert "width: 108" in content
    assert "scripts/orbit_status.py" in content
    assert '"--subscribe"' in content
    assert "SplitParser" in content
    assert 'root.displayState === "standby"' in content
    assert "drag.target: orbitWidget" in content
    assert "lastTapAt" in content
    assert "now - lastTapAt <= 500" in content
    assert "onPressed: function(mouse)" in content
    assert "root.toggleMute()" in content
    assert "scripts/jarvisctl.py" in content
    assert '"toggle"]' in content
    assert 'root.muted ? "MUTED · DOUBLE TAP"' in content
    assert 'property string activityLabel: "Ready"' in content
    assert 'payload.activity' in content
    assert 'root.activityLabel.toUpperCase()' in content


def test_aura_field_has_distinct_voice_states():
    content = (ORBIT / "AuraFieldOrbit.qml").read_text(encoding="utf-8")
    for state in ("listening", "thinking", "speaking", "connecting", "standby", "disabled"):
        assert f'orbitState === "{state}"' in content
    assert "amunozdev/voiceorbs" in content


def test_orbit_demo_cycles_all_states_without_live_service():
    helper = (ROOT / "scripts" / "orbit_status.py").read_text(encoding="utf-8")
    for state in ("idle", "connecting", "listening", "thinking", "speaking",
                  "standby", "error", "offline"):
        assert f"'{state}'" in helper
