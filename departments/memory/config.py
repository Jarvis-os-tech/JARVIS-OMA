"""Configuration for the Memory Department in JARVIS OS.
Manages database paths, Obsidian vault bindings, TTL rules, and thresholds.
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
class MemoryConfig:
    # Base department directory
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    state_dir: Path = field(init=False)
    
    # SQLite Database Path (Default to XDG or local data dir)
    db_path: Path = field(init=False)
    
    # Obsidian Vault Directory
    obsidian_vault_path: Path = field(init=False)
    
    # Filtering & Memory Thresholds
    min_importance_to_save: float = 0.35      # Under 0.35 is discarded as small talk
    ephemeral_default_ttl_seconds: int = 604800 # 7 days
    
    # Model Configuration
    api_key: Optional[str] = None
    
    def __post_init__(self):
        self.state_dir = self.base_dir / "state"
        
        # Load all root .env variables into environment if not present
        root_env = self.base_dir.parent.parent / ".env"
        env_vars = _load_env_file(root_env)
        for k, v in env_vars.items():
            if k not in os.environ and not v.startswith("PASTE_YOUR_"):
                os.environ[k] = v

        def _clean_key(k: Optional[str]) -> Optional[str]:
            if not k or k.startswith("PASTE_YOUR_") or k.startswith("<") or k.startswith("YOUR_"):
                return None
            return k.strip()

        # Load API key if present with proper priority and rotation fallbacks
        self.api_key = (
            _clean_key(os.getenv("GEMINI_API_KEY"))
            or _clean_key(env_vars.get("GEMINI_API_KEY"))
            or _clean_key(os.getenv("GEMINI_API_KEY_1"))
            or _clean_key(env_vars.get("GEMINI_API_KEY_1"))
            or _clean_key(os.getenv("GOOGLE_API_KEY"))
            or _clean_key(env_vars.get("GOOGLE_API_KEY"))
            or _clean_key(os.getenv("NVIDIA_NIM_API_KEY"))
            or _clean_key(env_vars.get("NVIDIA_NIM_API_KEY"))
            or _clean_key(os.getenv("NVIDIA_API_KEY"))
            or _clean_key(env_vars.get("NVIDIA_API_KEY"))
        )
        
        # Determine database path
        xdg_data = os.getenv("XDG_DATA_HOME")
        if xdg_data:
            data_root = Path(xdg_data) / "jarvis-oma" / "memory"
        else:
            data_root = Path.home() / ".local" / "share" / "jarvis-oma" / "memory"
        
        # Fallback to local repo memory dir if XDG does not exist yet
        if not xdg_data and not data_root.parent.exists():
            data_root = self.base_dir.parent.parent / "memory" / "data"
            
        self.db_path = data_root / "memory_graph.db"
        
        # Determine Obsidian Vault path
        vault_path = None
        # 1. Environment variable
        vault_env = os.getenv("JARVIS_OBSIDIAN_VAULT") or env_vars.get("JARVIS_OBSIDIAN_VAULT")
        if vault_env and Path(vault_env).exists():
            vault_path = Path(vault_env).resolve()

        # 2. Check ~/.config/jarvis-voice/config.toml or ~/.config/jarvis-oma/config.toml
        if not vault_path:
            for toml_path in [
                Path.home() / ".config" / "jarvis-voice" / "config.toml",
                Path.home() / ".config" / "jarvis-oma" / "config.toml",
                self.base_dir.parent.parent / "config.toml",
            ]:
                if toml_path.exists():
                    try:
                        import tomllib
                        with open(toml_path, "rb") as f:
                            data = tomllib.load(f)
                            cfg_vault = data.get("memory", {}).get("obsidian_vault")
                            if cfg_vault and Path(cfg_vault).exists():
                                vault_path = Path(cfg_vault).resolve()
                                break
                    except Exception:
                        pass

        # 3. Fallback to local repo memory dir
        if not vault_path:
            vault_path = self.base_dir.parent.parent / "memory" / "data" / "obsidian-vault"

        self.obsidian_vault_path = vault_path


config = MemoryConfig()
