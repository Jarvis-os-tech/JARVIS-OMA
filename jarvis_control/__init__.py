"""JARVIS OS Control & Information Retrieval Core.

Provides desktop control, policy gating, execution, key translation,
system discovery, browser retrieval, and Gemini tool schemas.
"""
from __future__ import annotations

__version__ = "0.1.0"

from typing import Any

from .config import Config
from .tools import (
    Executor,
    Policy,
    Denied,
    NeedsConfirmation,
    Result,
    TOOL_SCHEMAS,
    tools_for,
)
from .keys import normalise_key, normalise_mods
from .discovery import TOPICS, lookup
omarchy_help = lookup
from .page_text import SelectionError, read_selection, paste_text
from .security import child_env, redact_text
from .grounding import background_google_grounding, format_grounding_result

GATE_TOOLS = [
    {
        "name": "confirm_last",
        "description": "Confirm the held action after the user explicitly spoke a confirmation word or phrase. Pass the exact phrase heard.",
        "parameters": {
            "type": "object",
            "properties": {
                "heard_phrase": {
                    "type": "string",
                    "description": "The exact confirmation phrase spoken by the user (e.g. 'yes', 'confirm', 'proceed')."
                }
            },
            "required": ["heard_phrase"],
        }
    },
    {
        "name": "cancel_last",
        "description": "Cancel the held action waiting for confirmation because the user explicitly declined or cancelled.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        }
    }
]


def clean_schema(s: Any) -> Any:
    """Strip properties unsupported by Gemini's schema parser."""
    if not isinstance(s, dict):
        return s
    cleaned: dict[str, Any] = {}
    for k, v in s.items():
        if k in ("additionalProperties", "$schema"):
            continue
        if k == "enum" and isinstance(v, list):
            non_empty = [x for x in v if x != ""]
            cleaned[k] = non_empty if non_empty else ["none"]
        elif isinstance(v, dict):
            cleaned[k] = clean_schema(v)
        elif isinstance(v, list):
            cleaned[k] = [clean_schema(x) for x in v]
        else:
            cleaned[k] = v
    return cleaned


def to_gemini_tools(schemas: list[dict] | None = None) -> list[dict]:
    """Convert executor schemas to Gemini functionDeclarations."""
    fns = []
    for schema in schemas if schemas is not None else TOOL_SCHEMAS:
        fns.append({
            "name": schema["name"],
            "description": schema["description"],
            "parameters": clean_schema(schema["input_schema"]),
        })
    for tool in GATE_TOOLS:
        fns.append({
            "name": tool["name"],
            "description": tool["description"],
            "parameters": clean_schema(tool["parameters"]),
        })
    return [{"function_declarations": fns}]


__all__ = [
    "Config",
    "Executor",
    "Policy",
    "Denied",
    "NeedsConfirmation",
    "Result",
    "TOOL_SCHEMAS",
    "tools_for",
    "to_gemini_tools",
    "clean_schema",
    "GATE_TOOLS",
    "normalise_key",
    "normalise_mods",
    "TOPICS",
    "omarchy_help",
    "SelectionError",
    "read_selection",
    "paste_text",
    "child_env",
    "redact_text",
    "background_google_grounding",
    "format_grounding_result",
]
