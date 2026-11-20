"""Central environment loader for JARVIS OS.

Loads keys and credentials from .env files across the repository, departments,
and user configuration paths, establishing canonical fallbacks and aliases.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex

_PLACEHOLDER_PATTERN = re.compile(r"^(?:PASTE_|YOUR_|REPLACE_|TODO|<|\{)", re.IGNORECASE)


def is_placeholder(val: str | None) -> bool:
    """Return True if val is None, empty, or an unconfigured placeholder."""
    if not val:
        return True
    val = val.strip().strip("\"'")
    if not val:
        return True
    return bool(_PLACEHOLDER_PATTERN.search(val))


def find_env_file() -> Path | None:
    """Locate the canonical .env file in priority order."""
    if "JARVIS_ENV_PATH" in os.environ:
        explicit = Path(os.environ["JARVIS_ENV_PATH"])
        if explicit.is_file():
            return explicit

    # 1. Project root relative to this file
    repo_root = Path(__file__).resolve().parents[1]
    repo_env = repo_root / ".env"
    if repo_env.is_file():
        return repo_env

    # 2. Well-known user config locations
    xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    candidates = [
        xdg_config / "jarvis-voice" / ".env",
        xdg_config / "jarvis-voice" / "env",
        xdg_config / "omarchy-voice" / "env",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def parse_env_file(path: Path | str) -> dict[str, str]:
    """Parse a .env file safely without executing shell code."""
    path = Path(path)
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return values

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_val = line.split("=", 1)
        key = key.strip()
        if not key.isidentifier():
            continue
        # Strip quotes and whitespace
        val = raw_val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        values[key] = val
    return values


def load_jarvis_env(override_existing: bool = False) -> dict[str, str]:
    """Load the .env into os.environ with fallback resolution and key aliases.

    If override_existing is False, already-set environment variables take precedence,
    except when the existing value is an unconfigured placeholder string.
    """
    env_file = find_env_file()
    loaded_vars: dict[str, str] = {}
    if env_file:
        loaded_vars = parse_env_file(env_file)
        for k, v in loaded_vars.items():
            if override_existing or k not in os.environ or is_placeholder(os.environ.get(k)):
                if not is_placeholder(v):
                    os.environ[k] = v

    # Ensure Gemini Aliases & numbered rotation fallback
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if is_placeholder(gemini_key):
        for suffix in ("_1", "_2", "_3", "_4", "_5", "_6", "_7"):
            candidate = os.environ.get(f"GEMINI_API_KEY{suffix}")
            if candidate and not is_placeholder(candidate):
                os.environ["GEMINI_API_KEY"] = candidate
                break

    if "GEMINI_API_KEY" in os.environ and is_placeholder(os.environ.get("GOOGLE_API_KEY")):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

    # Ensure Groq Aliases
    groq_key = os.environ.get("GROQ_API_KEY")
    if is_placeholder(groq_key):
        for suffix in ("_1", "_2", "_3"):
            candidate = os.environ.get(f"GROQ_API_KEY{suffix}")
            if candidate and not is_placeholder(candidate):
                os.environ["GROQ_API_KEY"] = candidate
                break

    # Ensure NVIDIA NIM / NVIDIA API Key Aliases
    nim_key = os.environ.get("NVIDIA_NIM_API_KEY")
    nv_key = os.environ.get("NVIDIA_API_KEY")
    if is_placeholder(nim_key) and nv_key and not is_placeholder(nv_key):
        os.environ["NVIDIA_NIM_API_KEY"] = nv_key
    elif is_placeholder(nv_key) and nim_key and not is_placeholder(nim_key):
        os.environ["NVIDIA_API_KEY"] = nim_key

    # Ensure GitHub Token Aliases
    gh_token = os.environ.get("GH_TOKEN")
    github_token = os.environ.get("GITHUB_TOKEN")
    if is_placeholder(gh_token) and github_token and not is_placeholder(github_token):
        os.environ["GH_TOKEN"] = github_token
    elif is_placeholder(github_token) and gh_token and not is_placeholder(gh_token):
        os.environ["GITHUB_TOKEN"] = gh_token

    return dict(os.environ)


# Automatically load on module import
load_jarvis_env()
