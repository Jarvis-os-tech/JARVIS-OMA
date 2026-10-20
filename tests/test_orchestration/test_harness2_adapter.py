import json

from orchestration.harness2_adapter import Harness2Adapter


def test_adapter_is_optional_and_reports_components(tmp_path):
    adapter = Harness2Adapter(tmp_path / "h2", executable=None)
    status = adapter.status()
    assert status["installed"] is False
    assert "memory" in status["components"]
    assert status["mode"] == "optional_task_refinement"


def test_lessons_are_added_to_future_prompt_and_evidence_is_recorded(tmp_path):
    adapter = Harness2Adapter(tmp_path / "h2", executable="/opt/harness2")
    adapter.record_outcome(agent="hermes", task="plan task", state="completed", output="evidence")
    prompt = adapter.prepare_prompt("do work", agent="claude", workspace="/tmp/project")
    assert "JARVIS HARNESS² CONTEXT" in prompt
    assert "hermes task ended completed" in prompt
    records = [json.loads(line) for line in (tmp_path / "h2" / "lessons.jsonl").read_text().splitlines()]
    assert records[0]["agent"] == "hermes"
