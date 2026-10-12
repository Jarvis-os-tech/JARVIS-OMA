"""Dynamic configuration for the Jarvis voice agent.

Loads settings from TOML or JSON config files with sensible defaults.
All previously-hardcoded values become configurable through config files,
environment variables, or CLI arguments.

Priority (highest to lowest):
1. Explicit keyword overrides (from CLI args)
2. Environment variables (JARVIS_*)
3. Config file (~/.config/jarvis-oma/config.toml, ./config.toml, or ./config.json)
4. Built-in defaults
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    """Agent identity and persona settings."""
    name: str = 'Jarvis'
    system_instruction: str | None = None  # None = use default template
    voice: str = 'Aoede'
    model: str = 'gemini-3.8-live'


@dataclass
class AudioConfig:
    """Audio capture and playback parameters."""
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    input_frame_ms: int = 20
    output_frame_ms: int = 20
    queue_max_seconds: int = 10
    playback_latency_ms: int = 40
    capture_latency_ms: int = 20
    command_timeout: int = 8

    @property
    def input_frame_bytes(self) -> int:
        """Bytes per input frame: rate * frame_ms / 1000 * 2 (16-bit mono)."""
        return self.input_sample_rate * self.input_frame_ms // 1000 * 2

    @property
    def output_frame_bytes(self) -> int:
        """Bytes per output frame: rate * frame_ms / 1000 * 2 (16-bit mono)."""
        return self.output_sample_rate * self.output_frame_ms // 1000 * 2

    @property
    def queue_max_chunks(self) -> int:
        """Maximum number of output chunks in the playback queue."""
        chunk_duration = self.output_frame_ms / 1000
        return int(self.queue_max_seconds / chunk_duration) if chunk_duration > 0 else 500


@dataclass
class VADConfig:
    """Voice Activity Detection parameters for Gemini Live."""
    enabled: bool = True
    start_sensitivity: str = 'START_SENSITIVITY_HIGH'
    end_sensitivity: str = 'END_SENSITIVITY_LOW'
    prefix_padding_ms: int = 200
    silence_duration_ms: int = 400
    activity_handling: str = 'START_OF_ACTIVITY_INTERRUPTS'


@dataclass
class SkillsConfig:
    """Skill system configuration."""
    enabled: bool = True
    manifest_dirs: list[str] | None = None  # None = use default bundled dir
    exclude_unavailable: bool = True  # Graceful degradation


@dataclass
class Config:
    """Root configuration container."""
    agent: AgentConfig = field(default_factory=AgentConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    commands: dict[str, str] = field(default_factory=dict)  # command overrides


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_toml(path: Path) -> dict:
    """Load a TOML file using the built-in tomllib (Python 3.11+)."""
    import tomllib
    with open(path, 'rb') as fh:
        return tomllib.load(fh)


def _load_json(path: Path) -> dict:
    """Load a JSON config file."""
    return json.loads(path.read_text(encoding='utf-8'))


_LOADERS = {
    '.toml': _load_toml,
    '.json': _load_json,
}


def _find_config_file() -> Path | None:
    """Auto-discover config file from standard locations."""
    # Explicit env var
    env_path = os.getenv('JARVIS_CONFIG')
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
        log.warning('JARVIS_CONFIG points to %s which does not exist', env_path)
        return None

    # Standard locations in priority order
    candidates = []

    # XDG config home
    xdg_config = os.getenv('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    candidates.append(Path(xdg_config) / 'jarvis-oma' / 'config.toml')
    candidates.append(Path(xdg_config) / 'jarvis-oma' / 'config.json')

    # Current working directory
    candidates.append(Path('config.toml'))
    candidates.append(Path('config.json'))

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _merge_section(target, data: dict):
    """Merge a dict into a dataclass, only setting known fields."""
    known = {f.name for f in fields(target)}
    for key, value in data.items():
        if key in known:
            current = getattr(target, key)
            expected_type = type(current) if current is not None else None
            # Type coercion for basic types
            if expected_type is int and isinstance(value, (int, float)) and not isinstance(value, bool):
                value = int(value)
            elif expected_type is bool and isinstance(value, bool):
                pass
            elif expected_type is str and isinstance(value, str):
                pass
            setattr(target, key, value)
        else:
            log.warning('Unknown config key ignored: %s', key)


def _apply_env_overrides(config: Config):
    """Apply JARVIS_* environment variables as overrides."""
    env_map = {
        'JARVIS_AGENT_NAME': ('agent', 'name'),
        'JARVIS_VOICE': ('agent', 'voice'),
        'JARVIS_MODEL': ('agent', 'model'),
        'JARVIS_SYSTEM_INSTRUCTION': ('agent', 'system_instruction'),
        'GEMINI_LIVE_MODEL': ('agent', 'model'),  # backward compat
    }
    for env_key, (section, attr) in env_map.items():
        value = os.getenv(env_key)
        if value is not None:
            setattr(getattr(config, section), attr, value.strip())


def load_config(path: str | Path | None = None, **overrides: Any) -> Config:
    """Load configuration with full priority chain.

    Args:
        path: Explicit config file path. None triggers auto-discovery.
        **overrides: Direct keyword overrides (highest priority).
                     Use dotted keys like agent_name, agent_voice, etc.
    """
    config = Config()

    # 1. Load config file
    config_path = Path(path) if path else _find_config_file()
    if config_path is not None and config_path.is_file():
        suffix = config_path.suffix.lower()
        loader = _LOADERS.get(suffix)
        if loader is None:
            raise ValueError(f'Unsupported config file format: {suffix} (use .toml or .json)')
        try:
            data = loader(config_path)
        except Exception as error:
            raise ValueError(f'Cannot load config file {config_path}: {error}') from None

        if not isinstance(data, dict):
            raise ValueError(f'Config file must be a mapping, got {type(data).__name__}')

        # Merge sections
        for section_name in ('agent', 'audio', 'vad', 'skills'):
            section_data = data.get(section_name)
            if isinstance(section_data, dict):
                _merge_section(getattr(config, section_name), section_data)

        # Command overrides
        commands = data.get('commands')
        if isinstance(commands, dict):
            config.commands.update({
                str(k): str(v) for k, v in commands.items()
                if isinstance(k, str) and isinstance(v, str)
            })

        log.info('Loaded config from %s', config_path)

    # 2. Environment variable overrides
    _apply_env_overrides(config)

    # 3. Direct keyword overrides (highest priority)
    override_map = {
        'agent_name': ('agent', 'name'),
        'voice': ('agent', 'voice'),
        'model': ('agent', 'model'),
        'system_instruction': ('agent', 'system_instruction'),
        'skills_enabled': ('skills', 'enabled'),
    }
    for key, (section, attr) in override_map.items():
        if key in overrides and overrides[key] is not None:
            setattr(getattr(config, section), attr, overrides[key])

    return config
