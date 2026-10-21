import json

from orchestration.harness2_adapter import Harness2Adapter


def test_adapter_is_optional_and_reports_components(tmp_path):
    adapter = Harness2Adapter(tmp_path / "h2", executable=None)
    status = adapter.status()
    assert status["installed"] is False
    assert "memory" in status["components"]
    assert status["mode"] == "optional_task_refinement"


def test_outcomes_are_recorded_but_not_injected_into_future_prompts(tmp_path):
    adapter = Harness2Adapter(tmp_path / "h2", executable="/opt/harness2")
    adapter.record_outcome(agent="hermes", task="plan task", state="completed", output="evidence")
    prompt = adapter.prepare_prompt("do work", agent="claude", workspace="/tmp/project")
    assert prompt.startswith("Task\ndo work\n\nContext\nRelevant project background.")
    assert "Expected result\n- Add the required functionality" in prompt
    assert prompt.endswith("- Work only in the supplied workspace: /tmp/project")
    assert "hermes task ended completed" not in prompt
    assert "SHARED JARVIS MEMORY" not in prompt
    records = [json.loads(line) for line in (tmp_path / "h2" / "lessons.jsonl").read_text().splitlines()]
    assert records[0]["agent"] == "hermes"


def test_corrupt_lesson_history_is_not_added_to_task_prompt(tmp_path):
    root = tmp_path / "h2"
    root.mkdir()
    (root / "lessons.jsonl").write_text(
        '{"lesson":"keep this evidence"}\n{"lesson":\n', encoding="utf-8")

    adapter = Harness2Adapter(root, executable=None)
    prompt = adapter.prepare_prompt("continue", agent="opencode", workspace="/tmp/project")

    assert "keep this evidence" not in prompt
    assert prompt.startswith("Task\ncontinue\n\nContext\nRelevant project background.")
