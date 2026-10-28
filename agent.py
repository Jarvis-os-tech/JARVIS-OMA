#!/usr/bin/env python3
"""Run restored GitHub speech audio; retain the previous import API for tests."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if __name__ == '__main__':
    from core.stable_voice import main
    raise SystemExit(main())
else:
    import core.agent
    sys.modules[__name__] = core.agent
