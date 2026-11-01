"""Environment filtering for child processes that must not receive credentials."""
from __future__ import annotations

import os
import re

_SECRET_NAME = re.compile(
    r'(?:^|_)(?:API_?KEY|ACCESS_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIALS?)(?:_|$)',
    re.IGNORECASE,
)


def is_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME.search(name))


def sanitized_subprocess_env(source=None, **updates):
    """Copy an environment while excluding credential-bearing variables."""
    source = os.environ if source is None else source
    result = {name: value for name, value in source.items() if not is_secret_name(name)}
    result.update({name: value for name, value in updates.items() if value is not None})
    return result
