#!/usr/bin/env python3
"""Root entrypoint forwarding to core.agent."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import core.agent
sys.modules[__name__] = core.agent

if __name__ == '__main__':
    core.agent.main()
