import sys
from pathlib import Path

root = str(Path(__file__).resolve().parent.parent)
sys.path = [p for p in sys.path if p != root]
sys.path.insert(0, root)
