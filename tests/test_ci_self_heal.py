"""Unit and integration tests for JARVIS Autonomous CI/CD Self-Healing Engine."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from scripts.ci_self_heal import (
    AiHealer,
    FailureParser,
    GitManager,
    HeuristicHealer,
    run_test_command,
    self_heal_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_failure_parser_extracts_failed_tests_and_files():
    sample_output = """
============================= test session starts ==============================
collecting ... collected 2 items

tests/test_sample.py .F                                                  [100%]

=================================== FAILURES ===================================
__________________________________ test_fail ___________________________________

    def test_fail():
>       assert 1 == 2
E       AssertionError: assert 1 == 2

tests/test_sample.py:12: AssertionError
--------------------------------- Captured log ---------------------------------
File "ui/jarvis_drone/main.js", line 29, in createWindow
File "scripts/sample.py", line 42, in helper
=========================== short test summary info ============================
FAILED tests/test_sample.py::test_fail - AssertionError: assert 1 == 2
========================= 1 failed, 1 passed in 0.12s ==========================
"""
    parsed = FailureParser.parse_pytest_output(sample_output)

    assert "tests/test_sample.py::test_fail" in parsed["failed_tests"]
    assert any("AssertionError" in err for err in parsed["error_messages"])
    files = [ref["file"] for ref in parsed["file_references"]]
    assert any("ui/jarvis_drone/main.js" in f for f in files)


def test_heuristic_healer_fixes_syntax_colon(tmp_path, monkeypatch):
    test_file = tmp_path / "broken.py"
    # Missing colon after if condition
    test_file.write_text("def my_func():\n    if True\n        return 1\n")

    monkeypatch.setattr("scripts.ci_self_heal.REPO_ROOT", tmp_path)

    failure_info = {
        "file_references": [{"file": "broken.py", "line": 2, "exists": True}],
        "raw_tail": 'File "broken.py", line 2\n    if True\n           ^\nSyntaxError: expected \':\'',
        "error_messages": ["SyntaxError: expected ':'"]
    }

    healed = HeuristicHealer.attempt_heal(failure_info)
    assert len(healed) == 1
    assert healed[0]["file"] == "broken.py"
    
    # File should now have valid syntax with colon
    content = test_file.read_text()
    assert "if True:" in content


def test_ai_healer_prompt_structure_and_json_cleaning():
    healer = AiHealer(model_name="gemini-3.5-flash")
    failure_info = {
        "failed_tests": ["tests/test_calc.py::test_add"],
        "error_messages": ["AssertionError: assert 3 == 4"],
        "raw_tail": "AssertionError: assert 3 == 4",
        "file_references": []
    }
    files = {"calc.py": "def add(a, b): return a + b + 1"}

    prompt = healer._build_prompt(failure_info, files)
    assert "tests/test_calc.py::test_add" in prompt
    assert "AssertionError: assert 3 == 4" in prompt
    assert "calc.py" in prompt

    # Test JSON parsing with Markdown code fence stripping
    raw_response = '```json\n[{"file": "calc.py", "content": "def add(a, b): return a + b\\n"}]\n```'
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target = tmp_path / "calc.py"
        target.write_text(files["calc.py"])
        with patch("scripts.ci_self_heal.REPO_ROOT", tmp_path):
            applied = healer._apply_ai_repairs(raw_response, {"calc.py": files["calc.py"]})
            assert len(applied) == 1
            assert applied[0]["file"] == "calc.py"
            assert target.read_text().strip() == "def add(a, b): return a + b"


def test_ai_healer_rejects_invalid_syntax_in_patch(tmp_path, monkeypatch):
    healer = AiHealer()
    monkeypatch.setattr("scripts.ci_self_heal.REPO_ROOT", tmp_path)
    target = tmp_path / "module.py"
    target.write_text("x = 1\n")

    # Syntax error patch
    bad_response = '[{"file": "module.py", "content": "def broken_code(\\""}]'
    applied = healer._apply_ai_repairs(bad_response, {"module.py": "x = 1\n"})
    assert len(applied) == 0
    # Original file must remain untouched
    assert target.read_text() == "x = 1\n"


def test_git_loop_guard_detects_runaway_heals():
    with patch("subprocess.run") as mock_run:
        # 5 consecutive self-heal commits
        mock_run.return_value = MagicMock(
            stdout="111111 fix(ci): self-heal foo\n222222 fix(ci): self-heal bar\n333333 fix(ci): self-heal baz\n444444 fix(ci): self-heal qux\n555555 fix(ci): self-heal zap\n"
        )
        assert GitManager.check_infinite_loop_guard(max_consecutive=5) is False

        # Varied commit history
        mock_run.return_value = MagicMock(
            stdout="111111 fix(ci): self-heal foo\n222222 feat: new feature\n"
        )
        assert GitManager.check_infinite_loop_guard(max_consecutive=5) is True


def test_self_heal_pipeline_passing_immediately(tmp_path):
    report_file = tmp_path / "report.json"
    exit_code = self_heal_pipeline(
        test_cmd="python3 -c 'exit(0)'",
        max_attempts=3,
        auto_push=False,
        report_path=str(report_file)
    )
    assert exit_code == 0
    assert report_file.exists()
    data = json.loads(report_file.read_text())
    assert data["status"] == "PASSED"
    assert data["final_exit_code"] == 0


def test_self_heal_pipeline_heals_with_heuristic(tmp_path, monkeypatch):
    report_file = tmp_path / "report.json"
    test_file = tmp_path / "target_func.py"
    test_file.write_text("def my_check():\n    if True\n        return True\n")

    monkeypatch.setattr("scripts.ci_self_heal.REPO_ROOT", tmp_path)

    # Command tests compilation of the file
    test_cmd = f"python3 -m py_compile {test_file}"

    exit_code = self_heal_pipeline(
        test_cmd=test_cmd,
        max_attempts=2,
        auto_push=False,
        report_path=str(report_file)
    )

    assert exit_code == 0
    assert report_file.exists()
    data = json.loads(report_file.read_text())
    assert data["status"] == "HEALED"
    assert "if True:" in test_file.read_text()
