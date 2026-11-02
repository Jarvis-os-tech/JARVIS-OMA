"""Stable integration locations, independent of compiled release directories."""
import json
import os
from pathlib import Path


def locations():
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
    config = config_home/'jarvis-voice/hermes-integration.json'
    if config.exists():
        info=config.stat()
        if config.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size>8192:
            raise ValueError('Hermes integration locations must be private operator configuration')
        values=json.loads(config.read_text())
        if not isinstance(values,dict) or set(values)!={'project_root','goals_root','workers_root'}:
            raise ValueError('Invalid Hermes integration locations')
        if any(not isinstance(v,str) or not Path(v).is_absolute() for v in values.values()):
            raise ValueError('Integration locations must be absolute')
        return {k:Path(v).resolve() for k,v in values.items()}
    # Development fallback only. Installed releases receive explicit locations.
    project=Path(__file__).resolve().parents[1]
    return {'project_root':project,'goals_root':project/'.jarvis-learning/task-agents',
            'workers_root':project/'.jarvis-orchestration'}
