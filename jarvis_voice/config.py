"""Voice configuration and credential loading."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import stat
import tomllib

from jarvis_memory.config import MemoryConfig, load_config as load_memory_config

CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
STATE_HOME = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
RUNTIME_DIR = Path(os.environ.get('XDG_RUNTIME_DIR', STATE_HOME)) / 'jarvis'
SOCKET_PATH = RUNTIME_DIR / 'control.sock'
STATE_FILE = RUNTIME_DIR / 'state.json'
LEVEL_FILE = RUNTIME_DIR / 'level'
ENV_FILE = CONFIG_HOME / 'jarvis-voice' / 'env'


def dir_is_private(path: Path) -> bool:
    s = Path(path).stat()
    return s.st_uid == os.getuid() and stat.S_IMODE(s.st_mode) & 0o077 == 0


def load_env(api_key_env="GEMINI_API_KEY"):
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', CONFIG_HOME))
    env_file = config_home / 'jarvis-voice' / 'env'
    project_env = Path(__file__).resolve().parents[1] / '.env'
    
    for f in (env_file, project_env):
        if f.is_file():
            for line in f.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith('export '):
                    line = line[7:].strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                name, value = line.split('=', 1)
                name = name.strip()
                val = value.strip().strip('"\'')
                if name and val and name not in os.environ:
                    os.environ[name] = val

    # If GEMINI_API_KEY is not set directly, check numbered keys (e.g. GEMINI_API_KEY_1, GEMINI_API_KEY_4)
    if 'GEMINI_API_KEY' not in os.environ:
        for suffix in ('_1', '_4', '_3', '_5', '_2'):
            alt = f"GEMINI_API_KEY{suffix}"
            if alt in os.environ and os.environ[alt]:
                os.environ['GEMINI_API_KEY'] = os.environ[alt]
                break


@dataclass
class StandbyConfig:
    enabled: bool = True
    threshold: float = 0.05
    vad_threshold: float = 0.0

    def validate(self):
        if not isinstance(self.enabled, bool):
            raise ValueError('standby.enabled must be a boolean')
        for name in ('threshold', 'vad_threshold'):
            val = getattr(self, name)
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not (0.0 <= float(val) <= 1.0):
                raise ValueError(f'standby.{name} must be between 0.0 and 1.0')
        return self


@dataclass
class FillerMixingConfig:
    ducking_window_ms: int = 50
    local_buffer_precharge: int = 2

    def validate(self):
        if not isinstance(self.ducking_window_ms, int) or isinstance(self.ducking_window_ms, bool) or self.ducking_window_ms < 0:
            raise ValueError('fillers.mixing.ducking_window_ms must be a non-negative integer')
        if not isinstance(self.local_buffer_precharge, int) or isinstance(self.local_buffer_precharge, bool) or self.local_buffer_precharge < 0:
            raise ValueError('fillers.mixing.local_buffer_precharge must be a non-negative integer')
        return self


@dataclass
class FillerConfig:
    enable_local_fillers: bool = True
    filler_audio_dir: str = "~/.local/share/jarvis-oma/audio/fillers/"
    phrases: list = field(default_factory=lambda: [
        {"text": "humm", "file": "humm_thoughtful.pcm", "duration_ms": 800, "context": "generic_deep_thought"},
        {"text": "wait a sec", "file": "wait_sec_system.pcm", "duration_ms": 1100, "context": "system_mutation"},
        {"text": "let's see", "file": "lets_see_code.pcm", "duration_ms": 950, "context": "filesystem_grep"},
        {"text": "give me a moment", "file": "moment_agent.pcm", "duration_ms": 1400, "context": "sub_agent_spawn"},
    ])
    mixing: FillerMixingConfig = field(default_factory=FillerMixingConfig)

    def validate(self):
        if not isinstance(self.enable_local_fillers, bool):
            raise ValueError('fillers.enable_local_fillers must be a boolean')
        if not isinstance(self.filler_audio_dir, str):
            raise ValueError('fillers.filler_audio_dir must be a string')
        if not isinstance(self.phrases, list):
            raise ValueError('fillers.phrases must be a list of phrase mappings')
        self.mixing.validate()
        return self


@dataclass
class Config:
    model: str = 'gemini-3.8-live'
    voice: str = 'Aoede'
    device: str = ''  # Microphone source only
    output_device: str = ''  # Speaker sink; empty uses the system default
    barge_in: bool = False
    barge_in_min_rms: float = 0.004
    barge_in_echo_threshold: float = 0.45
    barge_in_vad_threshold: float = 0.50
    autostart_listening: bool = True
    greet_on_start: bool = True
    turn_silence_frames: int = 35
    language: str = 'en-US'
    language_codes: list = field(default_factory=lambda: ['en-US', 'en-IN', 'en-GB'])
    api_key_env: str = 'GEMINI_API_KEY'
    enable_tools: bool = True
    allow_shell: bool = False
    dry_run: bool = False
    tasks_enabled: bool = True
    vision_enabled: bool = False
    control: dict = field(default_factory=dict)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    standby: StandbyConfig = field(default_factory=StandbyConfig)
    fillers: FillerConfig = field(default_factory=FillerConfig)

    def validate(self):
        for name in ('barge_in', 'autostart_listening', 'greet_on_start', 'enable_tools',
                     'allow_shell', 'dry_run', 'tasks_enabled', 'vision_enabled'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'{name} must be a boolean')
        for name in ('model', 'voice', 'device', 'output_device', 'api_key_env', 'language'):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f'{name} must be a string')
        if not isinstance(self.language_codes, list) or not all(isinstance(c, str) and c.strip() for c in self.language_codes):
            raise ValueError('language_codes must be a list of string language codes')
        for name in ('barge_in_min_rms', 'barge_in_echo_threshold', 'barge_in_vad_threshold'):
            val = getattr(self, name)
            if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0:
                raise ValueError(f'{name} must be a positive number')
        if not isinstance(self.turn_silence_frames, int) or isinstance(self.turn_silence_frames, bool) or self.turn_silence_frames < 10:
            raise ValueError('turn_silence_frames must be an integer >= 10')
        if not self.model.strip() or not self.voice.strip() or not self.api_key_env.isidentifier():
            raise ValueError('model, voice and api_key_env must be valid nonempty values')
        control_config(self)
        self.memory.validate()
        self.standby.validate()
        self.fillers.validate()
        return self


def load() -> Config:
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', CONFIG_HOME))
    path = config_home / 'jarvis-voice' / 'config.toml'
    if path.exists():
        data = tomllib.loads(path.read_text())
        fillers_data = data.pop('fillers', None)
        voice_data = data.get('voice', None)
        if isinstance(voice_data, dict) and 'fillers' in voice_data:
            fillers_data = voice_data.pop('fillers')
            if 'voice' in voice_data:
                data['voice'] = voice_data['voice']
            else:
                data.pop('voice', None)
        if fillers_data and isinstance(fillers_data, dict):
            mixing_data = fillers_data.pop('mixing', {})
            mixing_cfg = FillerMixingConfig(**mixing_data) if isinstance(mixing_data, dict) else FillerMixingConfig()
            fillers_cfg = FillerConfig(**fillers_data, mixing=mixing_cfg)
        else:
            fillers_cfg = FillerConfig()

        unknown = set(data) - set(Config.__dataclass_fields__)
        if unknown:
            raise ValueError('Unsupported jarvis-voice setting: ' + ', '.join(sorted(unknown)))
        standby_data = data.pop('standby', {})
        standby_cfg = StandbyConfig(**standby_data) if isinstance(standby_data, dict) else StandbyConfig()
        data.pop('memory', None)
        return Config(**data, standby=standby_cfg, fillers=fillers_cfg, memory=load_memory_config(path).memory).validate()
    return Config(memory=load_memory_config().memory).validate()


def control_config(voice_config: Config):
    """One control configuration shared by the voice adapter and control CLI."""
    from jarvis_control.config import from_mapping
    from jarvis_control.tasks import validate_config as validate_tasks
    from jarvis_control.vision import settings as vision_settings

    if not isinstance(voice_config.control, dict):
        raise ValueError('control must be a table')
    config = from_mapping(voice_config.control, **{
        name: getattr(voice_config, name)
        for name in ('allow_shell', 'dry_run', 'tasks_enabled', 'vision_enabled')
    })
    if config.unknown_keys:
        raise ValueError('Unsupported control setting: ' + ', '.join(config.unknown_keys))
    validate_tasks(config)
    vision_settings(config)
    return config
