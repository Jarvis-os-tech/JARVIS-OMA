"""Open OAuth URLs visibly from the JARVIS desktop service."""
from __future__ import annotations

import shutil
import subprocess
import webbrowser

from core.secret_env import sanitized_subprocess_env


def open_url(url: str) -> bool:
    """Launch a visible browser using Omarchy first, then desktop fallbacks."""
    if not isinstance(url, str) or not url.startswith(('https://', 'http://localhost:', 'http://127.0.0.1:')):
        return False
    env = sanitized_subprocess_env()
    for command in ('omarchy-launch-webapp', 'xdg-open'):
        executable = shutil.which(command)
        if not executable:
            continue
        try:
            subprocess.Popen(
                [executable, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env, start_new_session=True,
            )
            return True
        except OSError:
            continue
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False
