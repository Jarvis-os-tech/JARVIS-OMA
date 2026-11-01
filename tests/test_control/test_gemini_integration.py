"""Tests for Gemini Live tool schema conversion and execution integration."""
from google.genai import types
from jarvis_control import tools_for, to_gemini_tools, Config
from jarvis_voice.daemon import build_instruction, live_config


def test_gemini_tool_declarations_and_instruction():
    config = Config()
    schemas = tools_for(config)
    gemini_tools = to_gemini_tools(schemas)
    assert len(gemini_tools) == 1
    assert "function_declarations" in gemini_tools[0]
    fns = gemini_tools[0]["function_declarations"]
    names = {f["name"] for f in fns}

    # Verify key control tools
    assert "hypr_dispatch" in names
    assert "send_shortcut" in names
    assert "launch_app" in names
    assert "type_text" in names
    assert "run_in_terminal" in names
    assert "compose_windows" in names

    # Verify key retrieval tools
    assert "omarchy_help" in names
    assert "system_query" in names
    assert "web_search" in names
    assert "open_page" in names
    assert "read_terminal" in names
    assert "read_screen" in names
    assert "hypr_query" in names

    # Verify gate tools
    assert "confirm_last" in names
    assert "cancel_last" in names

    # Instruction should reflect all attached tools
    inst = build_instruction(gemini_tools)
    assert f"CURRENT ATTACHED OS TOOLS ({len(names)} available)" in inst
    assert "hypr_dispatch" in inst
    assert "system_query" in inst

    # LiveConnectConfig validation
    connect_cfg = types.LiveConnectConfig(
        tools=gemini_tools,
        system_instruction=types.Content(parts=[types.Part.from_text(text=inst)]),
    )
    assert len(connect_cfg.tools[0].function_declarations) == len(names)
