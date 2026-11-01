"""Tests for system discovery and architecture map information retrieval."""
import pytest
from jarvis_control.discovery import TOPICS, lookup


def test_topics_complete():
    for expected in ("overview", "commands", "command_details", "shortcuts", "applications",
                     "dispatchers", "configuration", "plugins", "hooks"):
        assert expected in TOPICS


def test_overview_lookup():
    ok, text = lookup("overview")
    assert ok is True
    assert "System" in text
    assert "Omarchy" in text


def test_commands_lookup():
    ok, text = lookup("commands", "audio")
    assert ok is True
    assert "audio" in text.lower()


def test_invalid_topic_rejected():
    ok, text = lookup("nonexistent_topic")
    assert ok is False
    assert "Unknown topic" in text


def test_bundled_omarchy_skill_guide_search():
    ok, text = lookup('skills', 'theme', limit=5)
    assert ok
    assert 'theme' in text.lower()
    assert '.md:' in text


def test_omarchy_skill_topic_is_exposed_to_provider():
    from jarvis_control import tools_for, Config
    schema = next(tool for tool in tools_for(Config()) if tool['name'] == 'omarchy_help')
    assert 'skills' in schema['input_schema']['properties']['topic']['enum']
    assert 'required' not in schema['input_schema'] or 'query' not in schema['input_schema']['required']


def test_omarchy_help_tool_execution_without_query():
    from jarvis_control.tools import Executor, Config
    executor = Executor(Config())
    res = executor.call("omarchy_help", {"topic": "commands", "limit": 5})
    assert res.ok is True
    assert "commands:" in res.output
    assert "entries" in res.output

