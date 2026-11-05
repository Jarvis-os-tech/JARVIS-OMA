"""Test sovereign Obsidian vault layout: unified conversations, personal data, and performance tracking."""
import json
import re
import tempfile
from pathlib import Path
import unittest

from jarvis_memory.config import MemoryConfig
from jarvis_memory.bridge import MemoryBridge


class SovereignMemoryLayoutTests(unittest.TestCase):
    def test_sovereign_vault_structure_and_single_conversations_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / 'state'
            vault = root / 'vault'
            vault.mkdir()

            config = MemoryConfig(
                path=str(state_dir),
                obsidian_vault=str(vault),
                obsidian_layout="sovereign",
                obsidian_auto_sync=False,
            )
            memory = MemoryBridge(config)
            memory.start()

            # Record personal data
            memory.remember("Prefer concise English for voice replies", category="preferences")
            memory.remember("Give me testing voice commands every time you update features", category="instructions")
            memory.remember("Only use local OAuth for GitHub and Google Workspace, never Composio", category="constraints")

            # Record conversation turns
            memory.record_exchange("Can you check my git status?", "Your branch is up to date.")
            memory.record_exchange("Please build the new memory feature.", "Working on the memory synchronization now.")

            # Sync to vault
            result = memory.sync_obsidian()
            self.assertEqual(result['status'], 'synced')

            # Verify folders at vault root
            folders = {p.name for p in vault.iterdir() if p.is_dir()}
            self.assertIn("Conversations", folders)
            self.assertIn("Personal", folders)
            self.assertIn("Performance", folders)
            self.assertIn("Knowledge", folders)
            # Must NOT have separate legacy/duplicate folders
            self.assertNotIn("Summaries", folders)
            self.assertNotIn("03 Episodic Memory", folders)
            self.assertNotIn("JARVIS-OMA Memory", folders)

            # 1) Everything creates a new md file in Conversations/
            conv_files = list((vault / "Conversations").glob("????-??-?? - *.md"))
            self.assertGreaterEqual(len(conv_files), 1)

            # 2) Stored with clean and structured summary + transcript
            conv_text = conv_files[0].read_text(encoding="utf-8")
            self.assertIn("Executive Summary", conv_text)
            self.assertIn("Chronological Dialogue Transcript", conv_text)
            self.assertIn("Can you check my git status?", conv_text)
            self.assertIn("Your branch is up to date.", conv_text)

            # 3) Conversations INDEX exists
            self.assertTrue((vault / "Conversations/INDEX.md").is_file())

            # 4) Separate folder for personal data: instructions, preferences, rules, identity
            self.assertTrue((vault / "Personal/Identity.md").is_file())
            self.assertTrue((vault / "Personal/Preferences.md").is_file())
            self.assertTrue((vault / "Personal/Instructions.md").is_file())
            self.assertTrue((vault / "Personal/Rules & Constraints.md").is_file())
            self.assertTrue((vault / "Personal/System & Environment.md").is_file())
            self.assertTrue((vault / "Personal/INDEX.md").is_file())

            rules_text = (vault / "Personal/Rules & Constraints.md").read_text(encoding="utf-8")
            self.assertIn("local OAuth", rules_text)
            self.assertIn("Voice Subsystem Lock", rules_text)

            # 5) Separate folder for failures and successes
            self.assertTrue((vault / "Performance/Successes.md").is_file())
            self.assertTrue((vault / "Performance/Failures & Issues.md").is_file())
            self.assertTrue((vault / "Performance/Optimizations.md").is_file())
            self.assertTrue((vault / "Performance/INDEX.md").is_file())

            # Master Dashboard 00 HOME.md
            home = vault / "00 HOME.md"
            self.assertTrue(home.is_file())
            home_text = home.read_text(encoding="utf-8")
            self.assertIn("[[Conversations/INDEX|", home_text)
            self.assertIn("[[Personal/INDEX|", home_text)
            self.assertIn("[[Performance/INDEX|", home_text)

            # Verify no broken wikilinks
            for md_file in vault.rglob("*.md"):
                text = md_file.read_text(encoding="utf-8")
                for link_target in re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', text):
                    target_path = vault / (link_target + ".md")
                    self.assertTrue(target_path.exists(), f"Broken link [[{link_target}]] in {md_file.name}")


if __name__ == '__main__':
    unittest.main()
