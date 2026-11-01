"""Read installed local agent paths without invoking package-manager wrappers."""
from pathlib import Path
import os
import shutil

_LAYOUT = {
    'codex': ('codex/latest/bin/codex',),
    'claude': ('claude/latest/claude',),
    'opencode': ('npm-opencode-cli/latest/node_modules/.bin/opencode',),
    'gemini': ('gemini/latest/node_modules/.bin/gemini',),
    'omp': ('github-can1357-oh-my-pi/latest/omp', 'oh-my-pi/latest/omp'),
    'pi': ('pi/latest/pi/pi',),
    'crush': ('crush/latest/crush', 'crush/latest/crush_*/crush'),
    'hermes': (),
}


def installed_executables(home=None):
    root = Path(home or Path.home()) / '.local/share/mise/installs'
    result = {}
    for agent, patterns in _LAYOUT.items():
        candidates = [path for pattern in patterns for path in root.glob(pattern)
                      if path.is_file() and os.access(path, os.X_OK)]
        result[agent] = str(candidates[0]) if candidates else shutil.which(agent)
    return result


def installed_path(home=None):
    root = Path(home or Path.home()) / '.local/share/mise/installs'
    entries = [str(Path(path).parent) for path in installed_executables(home).values() if path]
    node = root / 'node/latest/bin'
    if (node / 'node').is_file():
        entries.append(str(node))
    return os.pathsep.join(dict.fromkeys(entries + os.environ.get('PATH', '').split(os.pathsep)))
