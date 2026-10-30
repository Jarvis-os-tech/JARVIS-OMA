"""Sync configured memory to Obsidian without opening a voice connection."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import load_config
from jarvis_memory.bridge import MemoryBridge

memory = MemoryBridge(load_config().memory)
try:
    print(json.dumps(memory.sync_obsidian(), indent=2))
finally:
    memory.close()
