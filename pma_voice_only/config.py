"""Voice settings only. The old full application's feature flags are ignored."""
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tomllib

CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
STATE_HOME = Path(os.environ.get('XDG_STATE_HOME', Path.home()/'.local/state'))
RUNTIME_DIR = Path(os.environ.get('XDG_RUNTIME_DIR', STATE_HOME))/'omarchy-voice'
SOCKET_PATH = RUNTIME_DIR/'control.sock'
STATE_FILE = RUNTIME_DIR/'state.json'
LEVEL_FILE = RUNTIME_DIR/'level'
ENV_FILE = CONFIG_HOME/'omarchy-voice/env'

def dir_is_private(path):
    s = Path(path).stat()
    return s.st_uid == os.getuid() and stat.S_IMODE(s.st_mode) & 0o077 == 0

def load_env():
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            if line.strip().startswith('#') or '=' not in line:
                continue
            name, value = line.split('=',1)
            name = name.strip()
            if name in {'GEMINI_API_KEY', 'GOOGLE_API_KEY'} and name not in os.environ:
                os.environ[name] = value.strip().strip('\"\'')

@dataclass
class Config:
    model: str = 'gemini-3.8-live'
    voice: str = 'Puck'
    device: str = ''
    barge_in: bool = False
    autostart_listening: bool = True
    api_key_env: str = 'GEMINI_API_KEY'

def load():
    path = CONFIG_HOME/'pma-voice-only/config.toml'
    if path.exists():
        data = tomllib.loads(path.read_text())
        unknown = set(data) - set(Config.__dataclass_fields__)
        if unknown:
            raise ValueError('Unsupported voice-only setting: ' + ', '.join(sorted(unknown)))
        return Config(**data)
    # Import only audio preferences, never tools or desktop behavior.
    old = CONFIG_HOME/'omarchy-voice/config.toml'
    data = tomllib.loads(old.read_text()) if old.exists() else {}
    if data.get('provider', 'gemini') != 'gemini':
        raise ValueError('This isolated runtime supports the configured Gemini voice provider only')
    rt, ears = data.get('realtime',{}), data.get('ears',{})
    return Config(model=rt.get('model','gemini-3.8-live'), voice=rt.get('voice','Puck'),
                  device=ears.get('device',''), barge_in=ears.get('barge_in',False),
                  autostart_listening=ears.get('autostart_listening',True),
                  api_key_env=data.get('gemini',{}).get('api_key_env','GEMINI_API_KEY'))
