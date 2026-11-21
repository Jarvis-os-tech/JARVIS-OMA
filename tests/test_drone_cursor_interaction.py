"""
Unit tests for JARVIS Drone cursor interaction and dragging support.

Verifies:
1. Auto-dodge repulsive force is completely removed from index.html.
2. Eyes react ONLY when cursor is on the drone, with decreased reaction intensity.
3. When cursor is outside drone bounds, eye targets remain centered (0, 0).
4. Autonomous patrol is completely removed so the drone never drifts or changes position on its own.
5. Eye blinking and hover effects are strictly gated to when the cursor is on top of the drone.
6. Dragging is fully supported via pointer capture and bidirectional window/hitbox handlers.
7. Window positioning IPCs (set-window-position, move-window-by) are correctly registered in main.js.
"""

from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "ui" / "jarvis_drone" / "index.html"
MAIN_JS = REPO_ROOT / "ui" / "jarvis_drone" / "main.js"
PRELOAD_JS = REPO_ROOT / "ui" / "jarvis_drone" / "preload.js"


def test_autododge_and_patrol_are_completely_removed():
    """Verify that both auto-dodge and autonomous patrol drifting have been excised."""
    html_content = INDEX_HTML.read_text(encoding="utf-8")
    assert "dodgeForce" not in html_content, "dodgeForce must be completely removed"
    assert "cursorDist < 120" not in html_content, "Auto-dodge distance trigger must be removed"
    assert "patrolSpeed" not in html_content, "Autonomous patrol drift speed must be removed"
    assert "isPatrolling" not in html_content, "Autonomous patrol state must be removed"


def test_cursor_reacts_only_on_top_of_drone():
    """Verify that gaze tracking and blinking only activate when cursor is on top of drone."""
    html_content = INDEX_HTML.read_text(encoding="utf-8")

    # Verify boundaries and decreased amplitudes in index.html
    assert "isHoveringDrone" in html_content
    assert "targetEyeX = 0" in html_content
    assert "targetEyeY = 0" in html_content
    assert "stopBlinking" in html_content

    # Check maxEyeX and maxEyeY are decreased (<= 3.0 and <= 2.0 respectively, down from 7 and 4)
    matches_x = re.findall(r"const maxEyeX = ([\d.]+);", html_content)
    matches_y = re.findall(r"const maxEyeY = ([\d.]+);", html_content)
    assert matches_x, "maxEyeX must be defined"
    assert matches_y, "maxEyeY must be defined"

    for val in matches_x:
        assert float(val) <= 3.0, f"maxEyeX ({val}) should be decreased (<= 3.0)"
    for val in matches_y:
        assert float(val) <= 2.0, f"maxEyeY ({val}) should be decreased (<= 2.0)"


def test_dragging_interaction_wiring():
    """Verify dragging interaction has pointer capture and release handlers on both hitbox and window."""
    html_content = INDEX_HTML.read_text(encoding="utf-8")

    assert "hitbox.setPointerCapture" in html_content, "Hitbox must capture pointer on pointerdown"
    assert "hitbox.releasePointerCapture" in html_content, "Hitbox must release pointer on pointerup"
    assert "hitbox.addEventListener('pointerdown'" in html_content
    assert "hitbox.addEventListener('pointermove'" in html_content
    assert "hitbox.addEventListener('pointerup'" in html_content
    assert "window.addEventListener('pointerup'" in html_content, "Window pointerup fallback ensures drag is never stuck"


def test_main_js_and_preload_window_movement_support():
    """Verify main.js and preload.js expose window positioning and visibility controls."""
    main_content = MAIN_JS.read_text(encoding="utf-8")
    preload_content = PRELOAD_JS.read_text(encoding="utf-8")

    assert "ipcMain.on('set-window-position'" in main_content
    assert "ipcMain.on('move-window-by'" in main_content
    assert "ipcMain.handle('get-screen-bounds'" in main_content

    assert "setWindowPosition:" in preload_content
    assert "moveWindowBy:" in preload_content
    assert "getScreenBounds:" in preload_content


def test_compact_overlay_window_size():
    """Verify overlay window size is compact (96px) to eliminate transparent click-blocking zones."""
    main_content = MAIN_JS.read_text(encoding="utf-8")
    html_content = INDEX_HTML.read_text(encoding="utf-8")
    launch_sh = (REPO_ROOT / "ui" / "jarvis_drone" / "launch.sh").read_text(encoding="utf-8")

    assert "const WINDOW_SIZE = 96;" in main_content, "WINDOW_SIZE in main.js must be 96"
    assert "width: 96px;" in html_content, "is-electron stage width must be 96px"
    assert "height: 96px;" in html_content, "is-electron stage height must be 96px"
    assert "left: 48px;" in html_content, "drone anchor center must be 48px"
    assert "top: 48px;" in html_content, "drone anchor center must be 48px"
    assert "size 96 96" in launch_sh, "Hyprland windowrulev2 must specify size 96 96"


def test_no_square_tooltip_or_outline_on_hover():
    """Verify drone hitbox has no HTML title tooltip or focus outline box."""
    html_content = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="drone-hitbox" class="drone-hitbox">' in html_content, "drone-hitbox must not have a title tooltip attribute"
    assert "outline: none" in html_content, "CSS must suppress outlines"
