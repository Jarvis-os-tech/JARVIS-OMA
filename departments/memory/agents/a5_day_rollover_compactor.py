"""Agent 5: Day Rollover & Compactor Agent.
Event-driven: triggers when a new day file is born.
Strips bash/JSON dumps from yesterday's note, distills decisions,
carries forward unfinished tasks, and writes a clean executive summary to Obsidian & SQLite.
"""

from datetime import datetime, date
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from .base_memory_agent import BaseMemoryAgent, write_private_text as write_note

# Noise patterns to strip from raw daily notes
CODE_BLOCK_REGEX = re.compile(r"```(?:bash|sh|json|text|output)?[\s\S]*?```", re.MULTILINE)
JSON_PAYLOAD_REGEX = re.compile(r"\{[\s\S]*?\"(?:tool_name|exit_code|input)\"[\s\S]*?\}", re.MULTILINE)
FILLER_LINES_REGEX = re.compile(r"^(?:ok|okay|cool|test|echo|hello|thanks|got it)[\.!\?]?$", re.IGNORECASE | re.MULTILINE)
CHECKLIST_OPEN_REGEX = re.compile(r"^\s*-\s*\[\s*\]\s+(.*)$", re.MULTILINE)
CHECKLIST_DONE_REGEX = re.compile(r"^\s*-\s*\[[xX]\]\s+(.*)$", re.MULTILINE)


SYNC_CURSOR = re.compile(r"^<!-- memory-department-session-id: ([0-9a-f]{20}) (\d+) -->$", re.MULTILINE)


def is_compacted(content: str) -> bool:
    return bool(re.match(r"^---\n(?:(?!---\n)[^\n]*\n)*type: episodic_compacted_summary\n", content))


class DayRolloverCompactorAgent(BaseMemoryAgent):
    """The Event-Driven Day Rollover and Compaction Agent."""

    agent_id: str = "A5"
    agent_name: str = "DayRolloverCompactor"

    def _get_conversations_folder(self) -> Path:
        sovereign_dir = self.cfg.obsidian_vault_path.resolve() / "Conversations"
        if sovereign_dir.is_dir() and str(self.cfg.obsidian_vault_path.resolve()).rstrip("/") == "/home/g0pi/Documents/JARVIS Memory":
            if sovereign_dir.is_symlink():
                raise ValueError("Memory Department conversations folder must not be a symlink")
            return sovereign_dir
        folder = self.cfg.obsidian_vault_path.resolve() / "Memory Department" / "Conversations"
        if folder.resolve() != folder:
            raise ValueError("Memory Department conversations folder must not be a symlink")
        return folder

    def _resolve_daily_file(self, date_str: str) -> Optional[Path]:
        if date.fromisoformat(date_str).isoformat() != date_str:
            raise ValueError("Use YYYY-MM-DD for a daily note")
        folder = self._get_conversations_folder()
        return next((p for p in (folder / f"{date_str}.md", *sorted(folder.glob(f"{date_str} - *.md")))
                     if p.is_file() and not p.is_symlink()), None)

    def _get_today_filename(self, date_obj: date) -> str:
        """Format today's filename adhering to vault layout style."""
        conv_dir = self._get_conversations_folder()
        has_weekday_format = any(" - " in p.name for p in conv_dir.glob("????-??-?? - *.md"))
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
            date_match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?: - [A-Za-z]+)?\.md", p.name)
            if not date_match or p.is_symlink():
                continue
            try:
                candidate = date.fromisoformat(date_match[1]).isoformat()
            except ValueError:
                continue
            if candidate < today_str:
                dates.append(candidate)
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

        conv_dir = self._get_conversations_folder()
        today_filename = self._get_today_filename(now_date)
        today_file = self._resolve_daily_file(now_date.isoformat()) or conv_dir / today_filename

        # If today file already exists and last_date_str is today, no rollover needed
        if today_file.is_symlink():
            raise ValueError("Daily note must not be a symlink")
        if last_date_str == today_str and today_file.exists():
            return {"rollover_occurred": False, "active_date": today_str, "daily_file": str(today_file), "tasks_carried_count": 0}

        latest_prev = self._find_latest_previous_date(today_str)
        tasks_carried: List[str] = []
        if latest_prev:
            prev_file = self._resolve_daily_file(latest_prev)
            if prev_file and prev_file.exists():
                prev_content = prev_file.read_text(encoding="utf-8")
                tasks_carried = CHECKLIST_OPEN_REGEX.findall(prev_content)

        today_path = self.ensure_today_file(now_date)
        return {
            "rollover_occurred": True,
            "previous_date": latest_prev,
            "today_date": today_str,
            "daily_file": str(today_path),
            "new_daily_note": str(today_path),
            "tasks_carried_count": len(tasks_carried),
        }

    def ensure_today_file(self, target_date: Optional[date] = None) -> Path:
        """Ensure today's file exists TODAY. If not, compact yesterday immediately and create today's file.
        Also automatically compacts any past day files that remain uncompacted."""
        now_date = target_date or datetime.now().date()
        today_str = now_date.strftime("%Y-%m-%d")
        conv_dir = self._get_conversations_folder()
        today_filename = self._get_today_filename(now_date)
        today_file = self._resolve_daily_file(now_date.isoformat()) or conv_dir / today_filename

        self.compact_all_history(before=now_date)

        # 2. If today's file already exists, return it
        if today_file.is_symlink():
            raise ValueError("Daily note must not be a symlink")
        if today_file.exists():
            self.cfg.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            write_note(self.cfg.state_dir / "last_active_date.txt", today_str)
            return today_file

        # 3. Create today's file immediately today!
        latest_prev = self._find_latest_previous_date(today_str)
        tasks_carried = []
        if latest_prev:
            prev_file = self._resolve_daily_file(latest_prev)
            if prev_file and prev_file.exists():
                prev_content = prev_file.read_text(encoding="utf-8")
                tasks_carried = CHECKLIST_OPEN_REGEX.findall(prev_content)

        today_file = self._initialize_today_file(now_date, tasks_carried, latest_prev)

        last_date_file = self.cfg.state_dir / "last_active_date.txt"
        self.cfg.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_note(last_date_file, today_str)

        return today_file

    def _extract_all_dialogue_turns(self, content: str) -> Tuple[List[str], List[str]]:
        """Extract user statements and assistant responses from active notes, legacy notes, and transcripts."""
        user_statements: List[str] = []
        assistant_statements: List[str] = []

        # 1. Active note format: - `[07:01:24]` **User**: Clean the all widgets.
        active_user_re = re.compile(r"^-\s*`?\[\d{2}:\d{2}:\d{2}\]`?\s*\*\*User\*\*:\s*(.+)$", re.MULTILINE)
        active_asst_re = re.compile(r"^-\s*`?\[\d{2}:\d{2}:\d{2}\]`?\s*\*\*Jarvis\*\*:\s*(.+)$", re.MULTILINE)

        for match in active_user_re.finditer(content):
            text = match.group(1).strip()
            if text and not self._is_dialogue_noise(text):
                user_statements.append(text)

        for match in active_asst_re.finditer(content):
            text = match.group(1).strip()
            if text and len(text) > 8:
                assistant_statements.append(text)

        # 2. Legacy verbatim format: message 4774 (user), verbatim excerpt:\nJarvis, please do me a favor.
        legacy_re = re.compile(r"message\s+\d+\s*\((user|assistant)\),\s*verbatim excerpt:\s*\n+([^\n]+)", re.IGNORECASE)
        for match in legacy_re.finditer(content):
            role = match.group(1).lower()
            text = match.group(2).strip()
            if not text or self._is_dialogue_noise(text):
                continue
            if role == "user":
                user_statements.append(text)
            else:
                assistant_statements.append(text)

        # 3. Transcript format: ### [07:01:24] [User] — message 123\n\nClean the all widgets.
        trans_re = re.compile(r"###\s*\[\d{2}:\d{2}:\d{2}\]\s*\[(User|JARVIS)\][^\n]*\n+([^\n#]+)", re.MULTILINE)
        for match in trans_re.finditer(content):
            role = match.group(1).lower()
            text = match.group(2).strip()
            if not text or self._is_dialogue_noise(text):
                continue
            if "user" in role:
                user_statements.append(text)
            else:
                assistant_statements.append(text)

        return user_statements, assistant_statements

    def _is_dialogue_noise(self, text: str) -> bool:
        """Check if dialogue text is just filler or low-substance greeting."""
        t = text.strip().lower()
        if len(t) < 3:
            return True
        fillers = {
            "ok", "okay", "cool", "test", "echo", "hello", "hi", "hey",
            "thanks", "thank you", "got it", "yes", "no", "yep", "nope",
            "standby", "jarvis standby", "sure", "all right", "alright",
        }
        if t in fillers:
            return True
        words = t.split()
        if len(words) <= 2 and all(w in fillers for w in words):
            return True
        return False

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
        """Scrub noise from a historical file and build a rich executive summary, while preserving the full dialogue transcript."""
        folder = self._get_conversations_folder()
        if file_path.parent != folder or file_path.is_symlink():
            raise ValueError("Daily note must be inside the Memory Department conversations folder")

        raw_content = file_path.read_text(encoding="utf-8")
        if is_compacted(raw_content):
            return raw_content, CHECKLIST_OPEN_REGEX.findall(raw_content)

        backup_dir = folder / ".raw_backups"
        if backup_dir.is_symlink():
            raise ValueError("Daily note backup folder must not be a symlink")
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / file_path.name
        if backup.is_symlink():
            raise ValueError("Daily note backup must not be a symlink")

        if not backup.exists():
            write_note(backup, raw_content)
        source_content = raw_content

        raw_char_count = len(source_content)

        # Extract structured sections
        decisions = self._extract_section_items(source_content, "User decisions")
        preferences = self._extract_section_items(source_content, "User preferences")
        requests = self._extract_section_items(source_content, "User requests")
        other_user = self._extract_section_items(source_content, "Other user statements")
        outcomes = self._extract_section_items(source_content, "Assistant reported outcomes (unverified)")
        followups = self._extract_section_items(source_content, "Explicit follow-up mentions")
        open_tasks = CHECKLIST_OPEN_REGEX.findall(source_content)
        done_tasks = CHECKLIST_DONE_REGEX.findall(source_content)

        # Extract live dialogue turns
        dialogue_user, dialogue_asst = self._extract_all_dialogue_turns(source_content)

        # Merge extracted statements
        all_user_statements = []
        for s in requests + other_user + dialogue_user:
            s_clean = s.strip()
            if s_clean and s_clean not in all_user_statements and not self._is_dialogue_noise(s_clean):
                all_user_statements.append(s_clean)

        # Categorize user statements into directives/requests vs decisions/preferences
        for statement in all_user_statements:
            s_low = statement.lower()
            if any(s_low.startswith(w) for w in ["i prefer", "always", "never", "my name", "i like", "i want to use"]):
                if statement not in preferences:
                    preferences.append(statement)
            elif any(s_low.startswith(w) for w in ["let's", "decided", "confirm", "choose", "agreed"]):
                if statement not in decisions:
                    decisions.append(statement)
            else:
                if statement not in requests:
                    requests.append(statement)

        # Extract outcomes from assistant turns if outcomes section was sparse
        if len(outcomes) < 3 and dialogue_asst:
            for asst_text in dialogue_asst:
                if any(k in asst_text.lower() for k in ["cleared", "active", "restored", "saved", "completed", "cannot uninstall", "cannot remove"]):
                    if asst_text not in outcomes:
                        outcomes.append(asst_text[:140])

        # Extract dialogue transcript body to preserve forever in Obsidian
        transcript_body = ""
        if "## Chronological Dialogue Transcript" in source_content:
            transcript_body = source_content.split("## Chronological Dialogue Transcript", 1)[1].strip()
            if "[[Conversations/INDEX" in transcript_body:
                transcript_body = transcript_body.split("[[Conversations/INDEX", 1)[0].strip()
        elif "### 📝 Active Session Notes & Live Log" in source_content:
            transcript_body = source_content.split("### 📝 Active Session Notes & Live Log", 1)[1].strip()
        elif "## Conversation" in source_content:
            transcript_body = source_content.split("## Conversation", 1)[1].strip()
            if "[[Conversations/INDEX" in transcript_body:
                transcript_body = transcript_body.split("[[Conversations/INDEX", 1)[0].strip()
        else:
            match = re.search(r"(?:^-\s*`?\[\d{2}:\d{2}:\d{2}\]|###\s*\[\d{2}:\d{2}:\d{2}\])", source_content, re.MULTILINE)
            if match:
                transcript_body = source_content[match.start():].strip()
            else:
                transcript_body = ""

        transcript_body = SYNC_CURSOR.sub("", transcript_body).strip()
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
            f"# Daily Conversation & Executive Summary — {stem}",
            "",
            "## 📋 Executive Daily Summary",
            "",
        ]

        # 1. Key Requests & Tasks
        summary_lines.append("### 🎯 Key Requests & Focus")
        if requests:
            for r in requests[:8]:
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

        summary_text = "\n".join(summary_lines).rstrip()

        # Combine Executive Summary + Full Dialogue Transcript
        if transcript_body.strip():
            full_note_content = (
                summary_text + "\n\n"
                "---\n\n"
                "## 💬 Chronological Dialogue Transcript\n\n"
                + transcript_body.strip() + "\n\n"
                "---\n"
                "[[Conversations/INDEX|📁 Vault Conversations]] | [[00 HOME|🏠 Master Dashboard]]\n"
            )
        else:
            full_note_content = summary_text + "\n"

        cursors = {}
        for source, row_id in SYNC_CURSOR.findall(source_content):
            cursors[source] = max(int(row_id), cursors.get(source, 0))
        for source, row_id in cursors.items():
            full_note_content += f"\n<!-- memory-department-session-id: {source} {row_id} -->\n"

        compact_char_count = len(full_note_content)

        # Store in SQLite memory_nodes
        node_id = f"mem_epi_{date_str.replace('-', '')}"
        rel_obsidian_path = str(file_path.relative_to(self.cfg.obsidian_vault_path))
        self.db.upsert_node(
            node_id=node_id,
            layer="episodic",
            category="episode",
            title=f"Summary for {stem}",
            content=summary_text[:1200],
            importance=0.85,
            provenance="inferred_agent",
            obsidian_path=rel_obsidian_path,
        )

        self.db.log_rollover(
            date_str=date_str,
            raw_char_count=raw_char_count,
            compact_char_count=compact_char_count,
            tasks_carried=len(open_tasks),
            summary_preview=summary_text[:200],
        )

        self.logger.info(
            "Compacted %s: %d chars (summary: %d chars, transcript: %d chars, %d tasks)",
            stem,
            compact_char_count,
            len(summary_text),
            len(transcript_body),
            len(open_tasks),
        )

        write_note(file_path, full_note_content)
        return full_note_content, open_tasks

    def compact_date(self, target_date: str) -> Dict[str, Any]:
        if date.fromisoformat(target_date) >= date.today():
            raise ValueError("Only past daily notes can be compacted")
        path = self._resolve_daily_file(target_date)
        if path is None:
            raise ValueError(f"No Memory Department daily note for {target_date}")
        before = path.read_text(encoding="utf-8")
        summary, tasks = self._compact_single_file(path, target_date)
        return {"status": "COMPACTED" if summary != before else "ALREADY_COMPACTED",
                "date": target_date, "file": str(path), "tasks_carried": len(tasks)}

    def compact_all_history(self, before: Optional[date] = None) -> List[Dict[str, Any]]:
        """Compact past daily notes once, keeping a raw backup."""
        cutoff = (before or date.today()).isoformat()
        results = []
        folder = self._get_conversations_folder()
        for path in sorted(folder.glob("*.md")):
            match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?: - [A-Za-z]+)?\.md", path.name)
            if not match or match[1] >= cutoff or path.is_symlink() or not path.is_file():
                continue
            try:
                date.fromisoformat(match[1])
            except ValueError:
                continue
            original = path.read_text(encoding="utf-8")
            summary, tasks = self._compact_single_file(path, match[1])
            if summary != original:
                results.append({"filename": path.name, "date": match[1],
                                "tasks_carried": len(tasks), "summary_length": len(summary)})
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
        today_file = self._resolve_daily_file(now_date.isoformat()) or conv_dir / today_filename

        if today_file.is_symlink():
            raise ValueError("Daily note must not be a symlink")
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
            for task in tasks_carried:
                task = re.sub(r"\s+\*\(carried from \d{4}-\d{2}-\d{2}\)\*$", "", task)
                if task != "Standby for active tasks":
                    lines.append(f"- [ ] {task} *(carried from {prev_date_str})*")
        else:
            lines.append("- No open tasks carried over.")

        lines.extend([
            "",
            "### 📝 Active Session Notes & Live Log",
            f"- Session active at {datetime.now().strftime('%H:%M:%S')}.",
            "",
        ])

        conv_dir.mkdir(parents=True, exist_ok=True)
        write_note(today_file, "\n".join(lines))
        self.logger.info("Initialized new daily note: %s", today_file)

        # Update Conversations/INDEX.md if it exists
        self._update_conversations_index(today_filename)

        return today_file

    def _update_conversations_index(self, today_filename: str) -> None:
        """Ensure today's file is linked at the top of Conversations/INDEX.md."""
        conv_dir = self._get_conversations_folder()
        index_file = conv_dir / "INDEX.md"
        if index_file.is_symlink() or not index_file.exists():
            return

        stem = today_filename.removesuffix(".md")
        link_line = f"- [[Memory Department/Conversations/{stem}|{stem}]]"
        content = index_file.read_text(encoding="utf-8")
        if link_line not in content:
            marker = "## Recorded Days\n"
            if marker in content:
                parts = content.split(marker, 1)
                updated = parts[0] + marker + "\n" + link_line + "\n" + parts[1].lstrip()
            else:
                updated = content.rstrip() + f"\n{link_line}\n"
            write_note(index_file, updated)
            self.logger.info("Updated Conversations/INDEX.md with link to %s", stem)
