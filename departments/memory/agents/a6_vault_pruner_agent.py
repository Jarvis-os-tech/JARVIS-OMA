"""Agent 6: Vault Pruner & Empty File Cleaner Agent.
Sole Mandate: Scans the Obsidian vault to detect and remove empty markdown files,
whitespace-only files, and blank stubs, ensuring clean indices with no broken wikilinks.
"""

from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set

from .base_memory_agent import BaseMemoryAgent
from .a5_day_rollover_compactor import SYNC_CURSOR

PROTECTED_NAMES = {"00 HOME.md", "INDEX.md"}
IGNORED_DIRS = {".obsidian", ".raw_backups", ".git"}


class VaultPrunerAgent(BaseMemoryAgent):
    """Specialist agent solely dedicated to purging empty markdown files from the vault."""

    agent_id: str = "A6"
    agent_name: str = "VaultPruner"

    def prune_empty_files(
        self,
        vault_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Scan the vault and delete empty, whitespace-only, or blank stub markdown files."""
        root = vault_path or self.cfg.obsidian_vault_path
        if not root or not root.is_dir():
            return {"status": "ERROR", "reason": "Vault path does not exist", "pruned_files": []}

        today_str = datetime.now().strftime("%Y-%m-%d")
        pruned_files: List[str] = []
        bytes_freed = 0
        removed_stems: Set[str] = set()
        failed_files: List[str] = []

        for md_path in sorted(root.rglob("*.md")):
            # 1. Skip protected directories
            rel_parts = md_path.relative_to(root).parts
            if any(part in IGNORED_DIRS or part.startswith(".") for part in rel_parts):
                continue

            # 2. Skip protected root files
            if md_path.is_symlink() or md_path.name in PROTECTED_NAMES:
                continue

            # 3. Protect today's active note even if it only has initial template
            if md_path.name.startswith(today_str):
                continue

            # 4. Check if file is empty or blank stub
            is_empty, reason = self._is_empty_or_blank_stub(md_path)
            if is_empty:
                size = md_path.stat().st_size
                if not dry_run:
                    try:
                        md_path.unlink()
                    except OSError as error:
                        failed_files.append(str(md_path.relative_to(root)))
                        self.logger.warning("Could not delete %s: %s", md_path, error)
                        continue
                pruned_files.append(f"{md_path.relative_to(root)} ({reason})")
                removed_stems.add(md_path.stem)
                bytes_freed += size

        # 5. Clean up any dangling wikilinks in INDEX.md
        if not dry_run and removed_stems:
            self._cleanup_dangling_index_links(root, removed_stems)

        return {
            "status": "ERROR" if failed_files else "COMPLETED",
            "failed_files": failed_files,
            "dry_run": dry_run,
            "pruned_count": len(pruned_files),
            "bytes_freed": bytes_freed,
            "pruned_files": pruned_files,
        }

    def _is_empty_or_blank_stub(self, file_path: Path) -> tuple[bool, str]:
        """Determine if a file is 0-byte, whitespace-only, or contains zero meaningful text."""
        try:
            stat = file_path.stat()
            # Case 1: 0-byte file
            if stat.st_size == 0:
                return True, "0-byte file"

            content = file_path.read_text(encoding="utf-8")
            if SYNC_CURSOR.search(content):
                return False, "contains a session sync checkpoint"

            # Case 2: Whitespace only
            if not content.strip():
                return True, "whitespace only"

            # Strip YAML frontmatter
            stripped = content
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    stripped = parts[2].strip()

            # Strip HTML comments like <!-- marker -->
            stripped = re.sub(r"<!--[\s\S]*?-->", "", stripped).strip()

            # Strip single empty markdown headers like # Title with no content
            stripped = re.sub(r"^#+\s+.*$", "", stripped, flags=re.MULTILINE).strip()

            # Case 3: After stripping frontmatter, comments, and titles, nothing remains
            if not stripped:
                return True, "blank template without body"

            return False, "contains content"

        except Exception as e:
            self.logger.warning("Error inspecting file %s: %s", file_path, e)
            return False, f"error: {e}"

    def _cleanup_dangling_index_links(self, root: Path, removed_stems: Set[str]) -> None:
        """Remove links to deleted files from INDEX.md files in the vault."""
        for index_path in root.rglob("INDEX.md"):
            if index_path.is_symlink():
                continue
            try:
                text = index_path.read_text(encoding="utf-8")
                changed = False
                lines = []
                for line in text.splitlines():
                    # Only remove a standalone link entry, preserving surrounding prose.
                    entry = re.fullmatch(r"\s*(?:[-*+]\s+)?\[\[(?:Conversations/)?([^|\]]+)(?:\|[^\]]+)?\]\]\s*", line)
                    if entry and entry[1] in removed_stems:
                        changed = True
                        continue
                    lines.append(line)
                if changed:
                    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    self.logger.info("Cleaned dangling links from %s", index_path.relative_to(root))
            except Exception as e:
                self.logger.warning("Failed cleaning index %s: %s", index_path, e)
