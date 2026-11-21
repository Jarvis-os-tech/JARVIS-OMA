"""Unit tests for JARVIS Prompt Style engine and DesktopSkill integration."""
import pytest
from pathlib import Path
from orchestration.prompt_style import format_prompt, ROLE_GUIDELINES
from orchestration.harness2_adapter import Harness2Adapter
from orchestration.personas import software_assignments
from jarvis_control.omarchy_skill import guide_sections
from skills.skills import DesktopSkills


def test_format_prompt_basic():
    result = format_prompt("Fix the segfault in audio engine")
    assert result['status'] == 'success'
    text = result['formatted_prompt']
    assert "Task\nFix the segfault in audio engine" in text
    assert "Operating Principles (JARVIS / Omarchy Style)" in text
    assert "Expected Result" in text
    assert "Constraints" in text
    assert "audio/engine.py" in text


def test_format_prompt_with_role_and_context():
    result = format_prompt(
        task="Investigate memory spike",
        context="System journal reports OOM killer killed process 4120",
        constraints="Do not restart systemd daemon",
        role="triage",
        workspace="/home/g0pi/JARVIS OS"
    )
    assert result['status'] == 'success'
    text = result['formatted_prompt']
    assert "Evidence & Context\nSystem journal reports OOM killer killed process 4120" in text
    assert "coredumpctl info <pid>" in text
    assert "4-point report" in text
    assert "/home/g0pi/JARVIS OS" in text
    assert "Do not restart systemd daemon" in text


def test_format_prompt_invalid():
    with pytest.raises(ValueError):
        format_prompt("")
    with pytest.raises(ValueError):
        format_prompt("   ")


def test_harness2_prepare_prompt():
    adapter = Harness2Adapter()
    prompt = adapter.prepare_prompt("Implement new status widget", agent="claude", workspace="/tmp/workspace")
    assert "Task\nImplement new status widget" in prompt
    assert "Operating Principles (JARVIS / Omarchy Style)" in prompt
    assert "/tmp/workspace" in prompt
    assert "audio/engine.py" in prompt


def test_software_assignments_prompt_style():
    executables = {'hermes': '/bin/hermes', 'opencode': '/bin/opencode', 'claude': '/bin/claude'}
    assignments = software_assignments(executables)
    assert len(assignments) == 4
    hermes_prompt = assignments[0]['prompt']
    assert "Distinguish proven facts from inferences" in hermes_prompt
    dev_prompt = assignments[1]['prompt']
    assert "zero-polling architecture" in dev_prompt
    assert "~/.config overrides with backups" in dev_prompt
    qa_prompt = assignments[2]['prompt']
    assert "Work strictly from evidence" in qa_prompt


def test_omarchy_guide_sections_includes_prompt_style():
    sections = guide_sections()
    names = [name for name, _ in sections]
    assert any("prompt_style.md" in name for name in names)


@pytest.mark.asyncio
async def test_desktop_skills_format_agent_prompt():
    skills = DesktopSkills()
    assert "format_agent_prompt" in skills._skills
    declaration = next(d for d in skills.declarations if d['name'] == 'format_agent_prompt')
    assert "canonical Omarchy/JARVIS prompt style" in declaration['description']

    result = await skills._adapter_format_agent_prompt(
        task="Build headless CLI utility",
        role="coding",
        workspace="/home/g0pi/JARVIS OS"
    )
    assert result['status'] == 'success'
    assert "Task\nBuild headless CLI utility" in result['formatted_prompt']
    assert "Zero-polling rule" in result['formatted_prompt']
