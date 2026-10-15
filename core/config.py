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
    language: str = 'en'  # Primary language code (e.g. 'en', 'te', 'hi', or 'auto')
    greet_on_activation: bool = True  # Proactively greet user when activated
    greeting_prompt: str | None = None  # Custom greeting instruction if specified
    greeting_cooldown_seconds: int = 14400  # Suppress repeat startup greetings on the same day
    greeting_resume_work: bool = True  # Offer one continuation from saved conversation evidence
    single_sentence: bool = True  # Strictly enforce single-sentence responses


@dataclass
class AudioConfig:
    """Audio capture and playback parameters."""
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    input_frame_ms: int = 20
    output_frame_ms: int = 20
    queue_max_seconds: int = 10
    playback_latency_ms: int = 60
    capture_latency_ms: int = 30
    command_timeout: int = 8
    noise_suppression: bool = True
    mic_volume_percent: int | None = 80
    playback_cushion_s: float = 0.35
    voice_rms_threshold: float = 450.0
    voice_band_ratio: float = 0.55
    duck_after_ms: int = 40
    barge_in_after_ms: int = 300
    release_after_ms: int = 120
    duck_gain: float = 0.30
    fade_ms: int = 10

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
    start_sensitivity: str = 'START_SENSITIVITY_LOW'
    end_sensitivity: str = 'END_SENSITIVITY_LOW'
    prefix_padding_ms: int = 300
    silence_duration_ms: int = 800
    activity_handling: str = 'START_OF_ACTIVITY_INTERRUPTS'


@dataclass
class SkillsConfig:
    """Skill system configuration."""
    enabled: bool = True
    manifest_dirs: list[str] | None = None  # None = use default bundled dir
    exclude_unavailable: bool = False  # Graceful degradation


@dataclass
class FilesystemConfig:
    """Filesystem autonomy and capability parameters."""
    enabled: bool = True
    autonomous: bool = True  # Full autonomy flag
    allow_delete: bool = True  # Allow permanent deletion in addition to trash
    max_read_chars: int = 50000
    max_write_bytes: int = 5 * 1024 * 1024  # 5 MiB


@dataclass
class MemoryConfig:
    """Persistent memory and optional local background extraction settings."""
    enabled: bool = True
    path: str = ''  # Bridge resolves XDG_STATE_HOME/jarvis-oma/memory
    max_facts: int = 1000
    context_max_chars: int = 6000
    record_sessions: bool = True  # Continuous conversation memory across restarts
    auto_capture: bool = False
    extraction_model: str = ''
    extraction_url: str = 'http://127.0.0.1:11434'
    obsidian_vault: str = ''
    obsidian_auto_sync: bool = True
    obsidian_timezone: str = 'Asia/Kolkata'
    structured_capture: bool = True  # Local evidence-grounded extraction; no model required
    semantic_retrieval: bool = False  # Requires an explicitly configured embedding model
    semantic_provider: str = 'gemini'
    semantic_model: str = ''
    semantic_url: str = 'http://127.0.0.1:11434'
    semantic_dimension: int = 768
    semantic_min_score: float = 0.55

    def validate(self):
        for name in ('enabled', 'record_sessions', 'auto_capture', 'obsidian_auto_sync',
                     'structured_capture', 'semantic_retrieval'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'memory.{name} must be a boolean')
        for name in ('max_facts', 'context_max_chars'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'memory.{name} must be a positive integer')
        for name in ('path', 'extraction_model', 'extraction_url', 'obsidian_vault', 'obsidian_timezone',
                     'semantic_provider', 'semantic_model', 'semantic_url'):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f'memory.{name} must be a string')
        if self.semantic_provider not in ('gemini', 'ollama'):
            raise ValueError('memory.semantic_provider must be gemini or ollama')
        if (isinstance(self.semantic_min_score, bool) or
                not isinstance(self.semantic_min_score, (int, float)) or
                not 0 <= self.semantic_min_score <= 1):
            raise ValueError('memory.semantic_min_score must be a number from 0 to 1')
        if (isinstance(self.semantic_dimension, bool) or
                not isinstance(self.semantic_dimension, int) or
                not 1 <= self.semantic_dimension <= 65536):
            raise ValueError('memory.semantic_dimension must be an integer from 1 to 65536')
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(self.obsidian_timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError('memory.obsidian_timezone must be a valid IANA timezone') from error
        if self.auto_capture and not self.extraction_model.strip():
            raise ValueError('memory.auto_capture requires a nonempty memory.extraction_model')
        if self.semantic_retrieval and not self.semantic_model.strip():
            raise ValueError('memory.semantic_retrieval requires memory.semantic_model')


@dataclass
class Config:
    """Root configuration container."""
    agent: AgentConfig = field(default_factory=AgentConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    filesystem: FilesystemConfig = field(default_factory=FilesystemConfig)
    commands: dict[str, str] = field(default_factory=dict)  # command overrides
    memory: MemoryConfig = field(default_factory=MemoryConfig)


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
            elif expected_type is float and isinstance(value, (int, float)) and not isinstance(value, bool):
                value = float(value)
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
        'JARVIS_LANGUAGE': ('agent', 'language'),
        'JARVIS_SYSTEM_INSTRUCTION': ('agent', 'system_instruction'),
        'GEMINI_LIVE_MODEL': ('agent', 'model'),  # backward compat
        'JARVIS_FS_AUTONOMOUS': ('filesystem', 'autonomous'),
        'JARVIS_FS_ALLOW_DELETE': ('filesystem', 'allow_delete'),
        'JARVIS_FS_MAX_READ_CHARS': ('filesystem', 'max_read_chars'),
        'JARVIS_GREET_ON_ACTIVATION': ('agent', 'greet_on_activation'),
        'JARVIS_GREETING_PROMPT': ('agent', 'greeting_prompt'),
        'JARVIS_SINGLE_SENTENCE': ('agent', 'single_sentence'),
        'JARVIS_NOISE_SUPPRESSION': ('audio', 'noise_suppression'),
        'JARVIS_MIC_VOLUME_PERCENT': ('audio', 'mic_volume_percent'),
        'JARVIS_PLAYBACK_CUSHION_S': ('audio', 'playback_cushion_s'),
        'JARVIS_VAD_ACTIVITY_HANDLING': ('vad', 'activity_handling'),
        'JARVIS_MEMORY_ENABLED': ('memory', 'enabled'),
        'JARVIS_MEMORY_PATH': ('memory', 'path'),
    }
    for env_key, (section, attr) in env_map.items():
        value = os.getenv(env_key)
        if value is not None:
            target_obj = getattr(config, section)
            curr = getattr(target_obj, attr)
            if env_key == 'JARVIS_MEMORY_ENABLED':
                normalized = value.strip().lower()
                if normalized not in ('true', '1', 'yes', 'false', '0', 'no'):
                    raise ValueError('JARVIS_MEMORY_ENABLED must be a boolean (true/false, 1/0, yes/no)')
                val = normalized in ('true', '1', 'yes')
            elif isinstance(curr, bool):
                val = value.strip().lower() in ('true', '1', 'yes')
            elif isinstance(curr, int):
                try:
                    val = int(value.strip())
                except ValueError:
                    continue
            elif isinstance(curr, float):
                try:
                    val = float(value.strip())
                except ValueError:
                    continue
            else:
                val = value.strip()
            setattr(target_obj, attr, val)

    if os.getenv('JARVIS_NO_INTERRUPT', '').strip().lower() in ('true', '1', 'yes'):
        config.vad.activity_handling = 'NO_INTERRUPTION'


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
        for section_name in ('agent', 'audio', 'vad', 'skills', 'filesystem', 'memory'):
            section_data = data.get(section_name)
            if section_name == 'memory' and section_name in data and not isinstance(section_data, dict):
                raise ValueError('memory section must be a mapping')
            if isinstance(section_data, dict):
                if section_name == 'memory':
                    for key, value in section_data.items():
                        if key in {f.name for f in fields(MemoryConfig)}:
                            setattr(config.memory, key, value)
                        else:
                            log.warning('Unknown config key ignored: %s', key)
                else:
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
        'language': ('agent', 'language'),
        'system_instruction': ('agent', 'system_instruction'),
        'skills_enabled': ('skills', 'enabled'),
        'fs_autonomous': ('filesystem', 'autonomous'),
        'fs_allow_delete': ('filesystem', 'allow_delete'),
        'greet_on_activation': ('agent', 'greet_on_activation'),
        'greeting_prompt': ('agent', 'greeting_prompt'),
        'single_sentence': ('agent', 'single_sentence'),
        'noise_suppression': ('audio', 'noise_suppression'),
        'mic_volume_percent': ('audio', 'mic_volume_percent'),
        'playback_cushion_s': ('audio', 'playback_cushion_s'),
        'activity_handling': ('vad', 'activity_handling'),
    }
    for key, (section, attr) in override_map.items():
        if key in overrides and overrides[key] is not None:
            setattr(getattr(config, section), attr, overrides[key])

    if overrides.get('no_interrupt'):
        config.vad.activity_handling = 'NO_INTERRUPTION'

    config.memory.validate()
    return config
