"""Voice configuration and credential loading."""
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tomllib

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


def load_env():
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', CONFIG_HOME))
    env_file = config_home / 'jarvis-voice' / 'env'
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            if line.strip().startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            name = name.strip()
            if name in {'GEMINI_API_KEY', 'GOOGLE_API_KEY'} and name not in os.environ:
                os.environ[name] = value.strip().strip('"\'')


@dataclass
class Config:
    model: str = 'gemini-3.8-live'
    voice: str = 'Aoede'
    device: str = ''
    barge_in: bool = False
    autostart_listening: bool = True
    greet_on_start: bool = True
    api_key_env: str = 'GEMINI_API_KEY'


def load() -> Config:
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', CONFIG_HOME))
    path = config_home / 'jarvis-voice' / 'config.toml'
    if path.exists():
        data = tomllib.loads(path.read_text())
        unknown = set(data) - set(Config.__dataclass_fields__)
        if unknown:
            raise ValueError('Unsupported jarvis-voice setting: ' + ', '.join(sorted(unknown)))
        return Config(**data)
    return Config()
