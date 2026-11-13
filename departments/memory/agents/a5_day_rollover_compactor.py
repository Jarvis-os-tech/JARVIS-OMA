"""Agent 5: Day Rollover & Compactor Agent.
Event-driven: triggers when a new day file is born.
Strips bash/JSON dumps from yesterday's note, distills decisions,
carries forward unfinished tasks, and writes a clean executive summary to Obsidian & SQLite.
"""

from datetime import datetime, date
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from .base_memory_agent import BaseMemoryAgent

# Noise patterns to strip from raw daily notes
CODE_BLOCK_REGEX = re.compile(r"```(?:bash|sh|json|text|output)?[\s\S]*?```", re.MULTILINE)
JSON_PAYLOAD_REGEX = re.compile(r"\{[\s\S]*?\"(?:tool_name|exit_code|input)\"[\s\S]*?\}", re.MULTILINE)
FILLER_LINES_REGEX = re.compile(r"^(?:ok|okay|cool|test|echo|hello|thanks|got it)[\.!\?]?$", re.IGNORECASE | re.MULTILINE)
CHECKLIST_OPEN_REGEX = re.compile(r"^\s*-\s*\[\s*\]\s+(.*)$", re.MULTILINE)
CHECKLIST_DONE_REGEX = re.compile(r"^\s*-\s*\[[xX]\]\s+(.*)$", re.MULTILINE)


class DayRolloverCompactorAgent(BaseMemoryAgent):
    """The Event-Driven Day Rollover and Compaction Agent."""

    agent_id: str = "A5"
    agent_name: str = "DayRolloverCompactor"

    def _get_conversations_folder(self) -> Path:
        """Find the conversations folder (either 'Conversations' or '03 Episodic Memory/Conversations')."""
        sovereign_dir = self.cfg.obsidian_vault_path / "Conversations"
        if sovereign_dir.is_dir():
            return sovereign_dir
        return self.ensure_obsidian_subfolder("03 Episodic Memory/Conversations")

    def _resolve_daily_file(self, date_str: str) -> Optional[Path]:
        """Find the daily file for a date, supporting '{date}.md' and '{date} - {weekday}.md'."""
        conv_dir = self._get_conversations_folder()
        direct = conv_dir / f"{date_str}.md"
        if direct.exists():
            return direct
        matches = list(conv_dir.glob(f"{date_str} - *.md"))
        if matches:
            return matches[0]
        return None

    def _get_today_filename(self, date_obj: date) -> str:
        """Format today's filename adhering to vault layout style."""
        conv_dir = self._get_conversations_folder()
        has_weekday_format = any(" - " in p.name for p in conv_dir.glob("2026-*.md"))
        if has_weekday_format:
            weekday = date_obj.strftime("%A")
            return f"{date_obj.strftime('%Y-%m-%d')} - {weekday}.md"
        return f"{date_obj.strftime('%Y-%m-%d')}.md"

    def _find_latest_previous_date(self, today_str: str) -> Optional[str]:
        """Find the latest date in Conversations before today."""
        conv_dir = self._get_conversations_folder()
        dates = []
        for p in conv_dir.glob("*.md"):
            if p.name.startswith("INDEX") or p.name.startswith("conversation"):
                continue
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", p.name)
            if date_match:
                d_str = date_match.group(1)
                if d_str < today_str:
                    dates.append(d_str)
        if dates:
            return sorted(dates)[-1]
        return None

    def check_and_rollover(
        self,
        target_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Check if date has rolled over. If so, compact yesterday and initialize today."""
        now_date = target_date or datetime.now().date()
        today_str = now_date.strftime("%Y-%m-%d")

        last_date_file = self.cfg.state_dir / "last_active_date.txt"
        last_date_str = last_date_file.read_text(encoding="utf-8").strip() if last_date_file.exists() else None

        # If last_date_str is not recorded yet, discover the most recent recorded date in vault
        if not last_date_str:
            last_date_str = self._find_latest_previous_date(today_str)

        conv_dir = self._get_conversations_folder()
        today_filename = self._get_today_filename(now_date)
        today_file = conv_dir / today_filename

        # If today file already exists and last_date_str is today, no rollover needed
        if last_date_str == today_str and today_file.exists():
            return {"rollover_occurred": False, "active_date": today_str, "daily_file": str(today_file)}

        self.logger.info("Day rollover detected: %s -> %s", last_date_str, today_str)

        tasks_carried: List[str] = []
        compacted_summary: str = ""

        # 1. Compact previous day's file if it exists
        if last_date_str and last_date_str != today_str:
            compacted_summary, tasks_carried = self._compact_previous_day(last_date_str)

        # 2. Initialize today's new file if not yet created
        new_file_path = self._initialize_today_file(now_date, tasks_carried, last_date_str)

        # 3. Update last active date
        last_date_file.write_text(today_str, encoding="utf-8")

        return {
            "rollover_occurred": True,
            "previous_date": last_date_str,
            "today_date": today_str,
            "tasks_carried_count": len(tasks_carried),
            "new_daily_note": str(new_file_path),
            "summary_preview": compacted_summary[:150] if compacted_summary else "No previous note to compact",
        }

    def _extract_section_items(self, content: str, heading: str) -> List[str]:
        """Extract clean item lines from a markdown section ## heading."""
        items: List[str] = []
        pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
        match = pattern.search(content)
        if not match:
            return items
        start = match.end()
        next_heading = re.search(r"^##\s+", content[start:], re.MULTILINE)
        end = start + next_heading.start() if next_heading else len(content)
        section_text = content[start:end]

        for line in section_text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(("message ", "<!--", "[Excerpt")):
                continue
            if "verbatim excerpt:" in line.lower() or "additional mentions" in line.lower():
                continue
            if len(line) < 4:
                continue
            if line not in items:
                items.append(line)
        return items

    def _compact_single_file(self, file_path: Path, date_str: str) -> Tuple[str, List[str]]:
        """Scrub noise from a historical file and build a rich executive summary."""
        raw_content = file_path.read_text(encoding="utf-8")
        raw_char_count = len(raw_content)

        # Extract structured sections
        decisions = self._extract_section_items(raw_content, "User decisions")
        preferences = self._extract_section_items(raw_content, "User preferences")
        requests = self._extract_section_items(raw_content, "User requests")
        outcomes = self._extract_section_items(raw_content, "Assistant reported outcomes (unverified)")
        followups = self._extract_section_items(raw_content, "Explicit follow-up mentions")
        open_tasks = CHECKLIST_OPEN_REGEX.findall(raw_content)
        done_tasks = CHECKLIST_DONE_REGEX.findall(raw_content)

        stem = file_path.stem

        summary_lines = [
            "---",
            f"aliases: [\"{stem}\"]",
            f"date: {date_str}",
            "type: episodic_compacted_summary",
            f"compacted_at: {datetime.now().isoformat()}",
            "tags: [jarvis-memory, conversation, daily-summary, compacted]",
            "---",
            "<!-- jarvis-oma-memory-generated:v2 -->",
            "",
            f"# Executive Daily Summary — {stem}",
            "",
        ]

        # 1. Key Requests & Tasks
        summary_lines.append("### 🎯 Key Requests & Focus")
        if requests:
            for r in requests[:6]:
                summary_lines.append(f"- {r}")
        elif done_tasks:
            for dt in done_tasks[:6]:
                summary_lines.append(f"- [x] {dt.strip()}")
        else:
            summary_lines.append("- General conversational turn and system queries.")
        summary_lines.append("")

        # 2. User Decisions
        if decisions:
            summary_lines.append("### ⚖️ User Decisions & Directives")
            for d in decisions[:6]:
                summary_lines.append(f"- {d}")
            summary_lines.append("")

        # 3. Preferences Noted
        if preferences:
            summary_lines.append("### 💡 Preferences & Environment")
            for p in preferences[:5]:
                summary_lines.append(f"- {p}")
            summary_lines.append("")

        # 4. Actions & Outcomes
        if outcomes:
            summary_lines.append("### 🛠️ Actions & System Outcomes")
            for o in outcomes[:5]:
                summary_lines.append(f"- {o}")
            summary_lines.append("")

        # 5. Follow-ups and Pending Tasks
        if followups or open_tasks:
            summary_lines.append("### 📌 Follow-Ups & Pending Items")
            for ot in open_tasks:
                summary_lines.append(f"- [ ] {ot.strip()}")
            for f in followups[:4]:
                summary_lines.append(f"- {f}")
            summary_lines.append("")

        compact_content = "\n".join(summary_lines).rstrip() + "\n"
        file_path.write_text(compact_content, encoding="utf-8")
        compact_char_count = len(compact_content)

        # Store in SQLite memory_nodes
        node_id = f"mem_epi_{date_str.replace('-', '')}"
        rel_obsidian_path = str(file_path.relative_to(self.cfg.obsidian_vault_path))
        self.db.upsert_node(
            node_id=node_id,
            layer="episodic",
            category="episode",
            title=f"Summary for {stem}",
            content=compact_content[:1200],
            importance=0.85,
            provenance="inferred_agent",
            obsidian_path=rel_obsidian_path,
        )

        self.db.log_rollover(
            date_str=date_str,
            raw_char_count=raw_char_count,
            compact_char_count=compact_char_count,
            tasks_carried=len(open_tasks),
            summary_preview=compact_content[:200],
        )

        self.logger.info(
            "Compacted %s: %d chars -> %d chars (%d tasks)",
            stem,
            raw_char_count,
            compact_char_count,
            len(open_tasks),
        )

        return compact_content, open_tasks

    def compact_all_history(self) -> List[Dict[str, Any]]:
        """Compact all historical daily files in Conversations, preserving raw copies in .raw_backups/."""
        conv_dir = self._get_conversations_folder()
        backup_dir = conv_dir / ".raw_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        today_str = datetime.now().strftime("%Y-%m-%d")
        results = []

        for p in sorted(conv_dir.glob("*.md")):
            if p.name.startswith("INDEX") or p.name.startswith("conversation") or p.name.startswith("."):
                continue
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", p.name)
            if not date_match:
                continue
            date_str = date_match.group(1)

            # Skip today's active file
            if date_str >= today_str:
                continue

            # 1. Back up original raw file
            backup_file = backup_dir / p.name
            if not backup_file.exists():
                shutil.copy2(p, backup_file)

            # 2. Extract and compact
            compacted_summary, tasks = self._compact_single_file(p, date_str)
            results.append({
                "filename": p.name,
                "date": date_str,
                "tasks_carried": len(tasks),
                "summary_length": len(compacted_summary),
            })

        return results

    def _compact_previous_day(self, prev_date_str: str) -> Tuple[str, List[str]]:
        """Scrub noise from yesterday's file and distill accomplishments & open tasks."""
        prev_file = self._resolve_daily_file(prev_date_str)
        if not prev_file or not prev_file.exists():
            return "", []
        return self._compact_single_file(prev_file, prev_date_str)

    def _initialize_today_file(
        self,
        now_date: date,
        tasks_carried: List[str],
        prev_date_str: Optional[str],
    ) -> Path:
        """Create today's new Obsidian daily note with template and carried tasks."""
        conv_dir = self._get_conversations_folder()
        today_filename = self._get_today_filename(now_date)
        today_file = conv_dir / today_filename

        if today_file.exists():
            return today_file

        today_str = now_date.strftime("%Y-%m-%d")
        weekday_str = now_date.strftime("%A")
        title_heading = f"Daily Log — {today_str} - {weekday_str}"

        lines = [
            "---",
            f"aliases: [\"{today_str} - {weekday_str}\"]",
            f"date: {today_str}",
            "type: episodic_daily_active",
            f"created_at: {datetime.now().isoformat()}",
            "tags: [jarvis-memory, conversation, daily-active]",
            "---",
            f"<!-- jarvis-oma-memory-generated:v1 -->",
            "",
            f"# {title_heading}",
            "",
            "### 📌 Carried Over Tasks",
        ]

        if tasks_carried and prev_date_str:
            for t in tasks_carried:
                lines.append(f"- [ ] {t} *(carried from {prev_date_str})*")
        else:
            lines.append("- [ ] Standby for active tasks")

        lines.extend([
            "",
            "### 📝 Active Session Notes & Live Log",
            f"- Session active at {datetime.now().strftime('%H:%M:%S')}.",
            "",
        ])

        today_file.write_text("\n".join(lines), encoding="utf-8")
        self.logger.info("Initialized new daily note: %s", today_file)

        # Update Conversations/INDEX.md if it exists
        self._update_conversations_index(today_filename)

        return today_file

    def _update_conversations_index(self, today_filename: str) -> None:
        """Ensure today's file is linked at the top of Conversations/INDEX.md."""
        conv_dir = self._get_conversations_folder()
        index_file = conv_dir / "INDEX.md"
        if not index_file.exists():
            return

        stem = today_filename.removesuffix(".md")
        link_line = f"- [[Conversations/{stem}|{stem}]]"
        content = index_file.read_text(encoding="utf-8")
        if link_line not in content:
            marker = "## Recorded Days\n"
            if marker in content:
                parts = content.split(marker, 1)
                updated = parts[0] + marker + "\n" + link_line + "\n" + parts[1].lstrip()
            else:
                updated = content.rstrip() + f"\n{link_line}\n"
            index_file.write_text(updated, encoding="utf-8")
            self.logger.info("Updated Conversations/INDEX.md with link to %s", stem)
