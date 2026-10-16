"""Register the configured vault while preserving existing Obsidian settings."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import load_config

vault = Path(load_config().memory.obsidian_vault).resolve(strict=True)
settings = Path.home() / '.config/obsidian/obsidian.json'
if not (vault / '.obsidian').is_dir():
    raise SystemExit('vault is not initialized')
original = settings.read_text(encoding='utf-8') if settings.exists() else '{}'
data = json.loads(original)
vaults = data.setdefault('vaults', {})
key = next((key for key, value in vaults.items() if value.get('path') == str(vault)),
           sha256(str(vault).encode()).hexdigest()[:16])
vaults[key] = {**vaults.get(key, {}), 'path': str(vault), 'ts': int(time.time() * 1000), 'open': True}
settings.parent.mkdir(parents=True, exist_ok=True)
fd, backup = tempfile.mkstemp(dir=settings.parent, prefix='obsidian-before-jarvis-', suffix='.json')
with os.fdopen(fd, 'w', encoding='utf-8') as stream:
    stream.write(original)
fd, pending = tempfile.mkstemp(dir=settings.parent, suffix='.tmp')
try:
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
    os.replace(pending, settings)
finally:
    Path(pending).unlink(missing_ok=True)
print(json.dumps({'registered_vault': str(vault), 'vault_id': key, 'settings_backup': backup}))
