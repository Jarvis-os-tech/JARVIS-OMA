"""Configuration for the LinkedIn Department in JARVIS OS.
Manages NVIDIA NIM API credentials, model routing, and storage paths.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional


def _load_env_file(env_path: Path) -> dict[str, str]:
    env_vars = {}
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip("\"'")
        except Exception:
            pass
    return env_vars


@dataclass
class LinkedInConfig:
    # Directory paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    state_dir: Path = field(init=False)
    references_dir: Path = field(init=False)
    review_queue_dir: Path = field(init=False)

    # API Configuration
    api_key: Optional[str] = None
    base_url: str = "https://integrate.api.nvidia.com/v1"
    timeout_seconds: int = 45
    max_retries: int = 3

    # Model Routing
    # Primary model (fast, crisp, high-cadence instruction & reasoning)
    model_primary: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    # Deep reasoning model (long-chain thinking)
    model_deep_reasoning: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    # Frontier flagship model for deep strategic audits
    model_flagship: str = "nvidia/nemotron-3-ultra-550b-a55b"

    def __post_init__(self):
        self.state_dir = self.base_dir / "state"
        self.references_dir = self.base_dir / "references"
        self.review_queue_dir = self.state_dir / "review_queue"

        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.review_queue_dir.mkdir(parents=True, exist_ok=True)

        def _clean_key(k: Optional[str]) -> Optional[str]:
            if not k or k.startswith("PASTE_YOUR_") or k.startswith("<") or k.startswith("YOUR_"):
                return None
            return k.strip()

        # Always preload root .env variables into environment if not present
        root_env = self.base_dir.parent.parent / ".env"
        loaded_root = _load_env_file(root_env)
        for k, v in loaded_root.items():
            if k not in os.environ and not v.startswith("PASTE_YOUR_"):
                os.environ[k] = v

        if not _clean_key(self.api_key):
            # 1. Environment variables
            self.api_key = _clean_key(os.getenv("NVIDIA_NIM_API_KEY")) or _clean_key(os.getenv("NVIDIA_API_KEY"))

        if not _clean_key(self.api_key):
            # 2. Look in JARVIS OS root .env
            self.api_key = _clean_key(loaded_root.get("NVIDIA_NIM_API_KEY")) or _clean_key(loaded_root.get("NVIDIA_API_KEY"))

        if not _clean_key(self.api_key):
            # 3. Look in local .env
            local_env = self.base_dir / ".env"
            loaded = _load_env_file(local_env)
            self.api_key = _clean_key(loaded.get("NVIDIA_NIM_API_KEY")) or _clean_key(loaded.get("NVIDIA_API_KEY"))


# Global default configuration instance
config = LinkedInConfig()
