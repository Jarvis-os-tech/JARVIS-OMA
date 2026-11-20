#!/usr/bin/env python3
"""One-time migration & backfill script for device-separated memory and conversations.

Creates:
  - ~/.local/state/jarvis/memory/pc/ (sessions.db, knowledge.db, history.md, transcripts/)
  - ~/.local/state/jarvis/memory/mobile/ (sessions.db, knowledge.db, history.md, transcripts/)
  - Symlinks in ~/JARVIS OS/conversations/{pc, mobile}

Separates existing historical turns into PC and Mobile channels and ensures real-time dual persistence.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import shutil
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("migrate_device_conversations")

MEM_ROOT = Path.home() / ".local/state/jarvis/memory"
PC_DIR = MEM_ROOT / "pc"
MOBILE_DIR = MEM_ROOT / "mobile"
WORKSPACE_CONV = Path("/home/g0pi/JARVIS OS/conversations")

MOBILE_MESSAGE_IDS = {1188, 1189, 1190, 1191}


def init_device_directories():
    PC_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    (PC_DIR / "transcripts").mkdir(parents=True, exist_ok=True, mode=0o700)
    MOBILE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    (MOBILE_DIR / "transcripts").mkdir(parents=True, exist_ok=True, mode=0o700)
    log.info("Initialized memory device directories at %s and %s", PC_DIR, MOBILE_DIR)

    WORKSPACE_CONV.mkdir(parents=True, exist_ok=True)
    for name, target in [("pc", PC_DIR), ("mobile", MOBILE_DIR)]:
        link = WORKSPACE_CONV / name
        if link.is_symlink() or link.exists():
            if link.is_symlink() and link.resolve() == target.resolve():
                continue
            if link.is_symlink() or link.is_file():
                link.unlink()
            elif link.is_dir():
                shutil.rmtree(link)
        link.symlink_to(target, target_is_directory=True)
        log.info("Linked %s -> %s", link, target)


def migrate_sessions():
    central_db = MEM_ROOT / "sessions.db"
    if not central_db.is_file():
        log.warning("No central sessions.db found at %s", central_db)
        return

    # Backup central db first
    backup_path = MEM_ROOT / "sessions.db.bak"
    shutil.copy2(central_db, backup_path)
    log.info("Created backup of central sessions.db at %s", backup_path)

    conn = sqlite3.connect(central_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch all sessions
    sessions = c.execute("SELECT * FROM sessions").fetchall()
    # Fetch all messages
    messages = c.execute("SELECT * FROM session_messages ORDER BY id ASC").fetchall()
    log.info("Loaded %d sessions and %d messages from central database", len(sessions), len(messages))

    # Classify messages
    pc_messages = []
    mobile_messages = []

    for msg in messages:
        msg_id = msg["id"]
        channel = msg["channel"]
        content = msg["content"]
        is_mobile = (
            msg_id in MOBILE_MESSAGE_IDS
            or channel == "mobile"
            or "Test memory from companion mobile app" in content
            or "bought fresh apples today" in content
        )
        if is_mobile:
            mobile_messages.append(msg)
        else:
            pc_messages.append(msg)

    log.info("Classified: %d PC messages, %d Mobile messages", len(pc_messages), len(mobile_messages))

    # Update central DB channels
    c.execute("UPDATE session_messages SET channel = 'pc' WHERE channel IN ('voice', '') OR channel IS NULL")
    for msg in mobile_messages:
        c.execute("UPDATE session_messages SET channel = 'mobile' WHERE id = ?", (msg["id"],))
    conn.commit()
    conn.close()
    log.info("Updated central sessions.db message channels")

    # Helper to setup device db
    schema = """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id    TEXT PRIMARY KEY,
            user_id       TEXT,
            display_name  TEXT DEFAULT '',
            channel_ids   TEXT DEFAULT '{}',
            created_at    REAL,
            last_activity REAL,
            metadata      TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS session_messages (
            id         INTEGER PRIMARY KEY,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            channel    TEXT DEFAULT '',
            timestamp  REAL,
            metadata   TEXT DEFAULT '{}',
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    """

    for dev_name, dev_dir, dev_msgs in [("pc", PC_DIR, pc_messages), ("mobile", MOBILE_DIR, mobile_messages)]:
        dev_db = dev_dir / "sessions.db"
        dconn = sqlite3.connect(dev_db)
        dconn.executescript(schema)
        # Copy sessions
        for s in sessions:
            dconn.execute(
                "INSERT OR REPLACE INTO sessions(session_id, user_id, display_name, channel_ids, created_at, last_activity, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (s["session_id"], s["user_id"], s["display_name"], s["channel_ids"], s["created_at"], s["last_activity"], s["metadata"])
            )
        # Copy messages
        dconn.execute("DELETE FROM session_messages")
        for m in dev_msgs:
            dconn.execute(
                "INSERT INTO session_messages(id, session_id, role, content, channel, timestamp, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (m["id"], m["session_id"], m["role"], m["content"], dev_name, m["timestamp"], m["metadata"])
            )
        dconn.commit()
        dconn.close()
        dev_db.chmod(0o600)
        log.info("Populated %s/sessions.db with %d messages", dev_name, len(dev_msgs))

        # Write history.md and transcripts
        history_file = dev_dir / "history.md"
        daily_transcripts: dict[str, list] = {}

        with history_file.open("w", encoding="utf-8") as hf:
            hf.write(f"# JARVIS {dev_name.upper()} Continuous Conversation History\n\n")
            hf.write(f"*Total conversation turns: {len(dev_msgs)}*\n\n---\n\n")

            for m in dev_msgs:
                ts = m["timestamp"] or 0
                dt = datetime.fromtimestamp(ts) if ts > 0 else datetime.now()
                ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")

                role_label = "User" if m["role"] == "user" else "JARVIS"
                content = m["content"].strip()
                hf.write(f"### [{ts_str}] {role_label}\n{content}\n\n")

                if date_str not in daily_transcripts:
                    daily_transcripts[date_str] = []
                daily_transcripts[date_str].append((time_str, role_label, content))

        log.info("Wrote %s with %d turns", history_file, len(dev_msgs))

        for date_str, turns in daily_transcripts.items():
            tfile = dev_dir / "transcripts" / f"{date_str}.md"
            with tfile.open("w", encoding="utf-8") as tf:
                tf.write(f"# Conversation Transcript - {date_str} ({dev_name.upper()})\n\n")
                for time_str, role_label, content in turns:
                    tf.write(f"### [{time_str}] {role_label}\n{content}\n\n")
        log.info("Wrote %d daily transcripts for %s", len(daily_transcripts), dev_name)


def migrate_knowledge():
    central_kdb = MEM_ROOT / "knowledge.db"
    if not central_kdb.is_file():
        log.warning("No central knowledge.db found at %s", central_kdb)
        return

    conn = sqlite3.connect(central_kdb)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Update source for apples fact
    c.execute("UPDATE entries SET source = 'mobile-conversation' WHERE text LIKE '%apples%'")
    conn.commit()

    rows = c.execute("SELECT * FROM entries").fetchall()
    conn.close()
    log.info("Central knowledge.db contains %d entries", len(rows))

    from jarvis_memory.knowledge import KnowledgeStore

    pc_store = KnowledgeStore(PC_DIR / "knowledge.db")
    mobile_store = KnowledgeStore(MOBILE_DIR / "knowledge.db")

    for r in rows:
        target_store = mobile_store if "apples" in r["text"].lower() or r["source"] == "mobile-conversation" else pc_store
        evidence = json.loads(r["evidence"]) if r["evidence"] else {}
        target_store.upsert(
            text=r["text"],
            kind=r["kind"],
            key=r["key"] or "",
            source=r["source"],
            evidence=evidence,
            confidence=r["confidence"] or 1.0,
        )
    log.info("Populated device knowledge.db stores")


def main():
    log.info("Starting sovereign device conversation migration...")
    init_device_directories()
    migrate_sessions()
    migrate_knowledge()
    log.info("Migration completed successfully!")


if __name__ == "__main__":
    main()
