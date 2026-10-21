"""Read-only import of sibling-agent sessions into universal-memory proposals.

Sources are always supplied explicitly.  The importer never searches a home
directory, mutates a source store, or promotes imported agent text to an
authoritative memory.  Each accepted message becomes a proposal carrying its
original identity and a stable content hash.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Iterable

from .scanner import InjectionScanner
from .service_facade import UniversalMemoryService


SUPPORTED_AGENTS = frozenset({"claude", "codex", "gemini", "opencode", "hermes", "omp"})
SUPPORTED_FORMATS = frozenset({"markdown", "jsonl", "hermes-sqlite"})
_MAX_SOURCE_BYTES = 16 * 1024 * 1024
_MAX_TEXT_CHARS = 16_000
_SECRET_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*\S+",
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,})\b",
    r"\b(?:AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|xox[baprs]-[0-9A-Za-z-]{20,})\b",
    r"\b[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)\s*=\s*\S+",
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\b(?:authorization|proxy-authorization)\s*:\s*bearer\s+\S+",
))


class SessionImportError(ValueError):
    """Invalid or unsafe sibling-session import request."""


@dataclass(frozen=True, slots=True)
class SessionSource:
    """One explicitly authorized sibling-session source."""

    agent: str
    path: Path | str
    format: str
    scope: str
    project: str = ""
    repository: str = ""

    def normalized(self) -> "SessionSource":
        agent = self.agent.casefold().strip()
        source_format = self.format.casefold().strip()
        if agent not in SUPPORTED_AGENTS:
            raise SessionImportError(f"unsupported agent: {self.agent}")
        if source_format not in SUPPORTED_FORMATS:
            raise SessionImportError(f"unsupported source format: {self.format}")
        if not isinstance(self.scope, str) or not self.scope.strip():
            raise SessionImportError("source scope must be nonempty")
        path = Path(self.path).expanduser().resolve(strict=True)
        if source_format == "hermes-sqlite" and not path.is_file():
            raise SessionImportError("Hermes SQLite source must be a file")
        if source_format != "hermes-sqlite" and not (path.is_file() or path.is_dir()):
            raise SessionImportError("session source must be a file or directory")
        return SessionSource(agent, path, source_format, self.scope.strip(),
                             self.project.strip(), self.repository.strip())


@dataclass(slots=True)
class ImportReport:
    proposed: int = 0
    duplicates: int = 0
    quarantined: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    proposal_ids: list[str] = field(default_factory=list)
    dry_run: bool = False

    def as_dict(self):
        return {"proposed": self.proposed, "duplicates": self.duplicates,
                "quarantined": self.quarantined, "skipped": self.skipped,
                "errors": list(self.errors), "proposal_ids": list(self.proposal_ids),
                "dry_run": self.dry_run}


@dataclass(frozen=True, slots=True)
class _Message:
    session_id: str
    message_id: str
    role: str
    text: str
    timestamp: float | None
    source_path: str
    checkpoint: int


class SiblingSessionImporter:
    """Convert explicit sibling stores into non-authoritative proposals."""

    def __init__(self, service: UniversalMemoryService, checkpoint_path: Path | str,
                 *, scanner=None, max_batch=100):
        if type(max_batch) is not int or not 1 <= max_batch <= 1000:
            raise SessionImportError("max_batch must be an integer from 1 to 1000")
        self.service = service
        self.checkpoint_path = Path(checkpoint_path)
        self.scanner = scanner or InjectionScanner()
        self.max_batch = max_batch

    def import_sources(self, sources: Iterable[SessionSource], *, dry_run=False):
        if type(dry_run) is not bool:
            raise SessionImportError("dry_run must be a boolean")
        report = ImportReport(dry_run=dry_run)
        normalized = []
        for source in sources:
            try:
                normalized.append(source.normalized())
            except (OSError, ValueError) as error:
                agent = getattr(source, "agent", "unknown")
                report.errors.append(f"{agent}:source: {type(error).__name__}")
        checkpoints = self._load_checkpoints()
        known_hashes = {record["source_hash"] for record in self.service.store.list(active_only=False)
                        if record.get("source_hash")}
        for source in normalized:
            key = self._source_key(source)
            prior = int(checkpoints.get(key, 0))
            highest = prior
            try:
                messages = self._messages(source, prior)
                for message in messages:
                    if report.proposed >= self.max_batch:
                        break
                    highest = max(highest, message.checkpoint)
                    outcome = self._import_message(source, message, known_hashes, dry_run)
                    if outcome == "duplicate":
                        report.duplicates += 1
                    elif outcome == "quarantined":
                        report.quarantined += 1
                    elif outcome == "skipped":
                        report.skipped += 1
                    else:
                        report.proposed += 1
                        if outcome:
                            report.proposal_ids.append(outcome)
                if not dry_run:
                    checkpoints[key] = highest
            except (OSError, UnicodeError, ValueError, sqlite3.Error, json.JSONDecodeError) as error:
                report.errors.append(f"{source.agent}:{Path(source.path).name}: {type(error).__name__}")
        if not dry_run:
            self._save_checkpoints(checkpoints)
        return report.as_dict()

    def _import_message(self, source, message, known_hashes, dry_run):
        text = " ".join(message.text.split()).strip()
        if not text or len(text) > _MAX_TEXT_CHARS:
            return "skipped"
        if self._contains_secret(text) or not self.scanner.scan(text).is_clean:
            return "quarantined"
        source_hash = sha256((source.agent + "\0" + message.session_id + "\0" +
                              message.message_id + "\0" + text).encode("utf-8")).hexdigest()
        if source_hash in known_hashes:
            return "duplicate"
        known_hashes.add(source_hash)
        if dry_run:
            return ""
        evidence = {"source_agent": source.agent, "session_id": message.session_id,
                    "message_id": message.message_id, "role": message.role,
                    "original_path": message.source_path, "project": source.project,
                    "repository": source.repository, "content_hash": source_hash}
        proposal = self.service.propose({
            "text": text, "kind": "observation", "source": f"sibling-session:{source.agent}",
            "evidence": evidence, "confidence": 0.5, "scope": source.scope,
            "author": message.role or source.agent, "agent_id": source.agent,
            "observed_at": message.timestamp, "authority": "agent",
            "sensitivity": "private", "source_hash": source_hash,
        }, [f"session:{source.agent}:{message.session_id}:{message.message_id}"])
        return proposal["id"]

    @staticmethod
    def _contains_secret(text):
        return any(pattern.search(text) for pattern in _SECRET_PATTERNS)

    def _messages(self, source, prior):
        if source.format == "markdown":
            return self._markdown_messages(source, prior)
        if source.format == "jsonl":
            return self._jsonl_messages(source, prior)
        return self._hermes_messages(source, prior)

    def _markdown_messages(self, source, prior):
        path = Path(source.path)
        files = [path] if path.is_file() else sorted(path.glob("*.md"))
        output = []
        for index, item in enumerate(files, 1):
            if index <= prior or item.name.startswith(".") or item.is_symlink():
                continue
            if item.stat().st_size > _MAX_SOURCE_BYTES:
                continue
            text = item.read_text(encoding="utf-8")
            date = re.search(r"(?m)^date:\s*([^\n]+)", text)
            timestamp = self._timestamp(date.group(1).strip()) if date else item.stat().st_mtime
            output.append(_Message(item.stem, "document", source.agent, text, timestamp,
                                   str(item), index))
        return output

    def _jsonl_messages(self, source, prior):
        path = Path(source.path)
        files = [path] if path.is_file() else sorted(path.rglob("*.jsonl"))
        output, sequence = [], 0
        for item in files:
            if item.name.startswith(".") or any(part.startswith(".") for part in item.relative_to(path if path.is_dir() else path.parent).parts):
                continue
            if item.is_symlink() or item.stat().st_size > _MAX_SOURCE_BYTES:
                continue
            session_id = item.stem
            with item.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    sequence += 1
                    if sequence <= prior:
                        continue
                    data = json.loads(line)
                    if data.get("type") == "session":
                        session_id = str(data.get("id") or session_id)
                        continue
                    message = data.get("message") if isinstance(data.get("message"), dict) else data
                    role = str(message.get("role") or data.get("role") or "agent")
                    if role not in {"user", "assistant"}:
                        continue
                    text = self._content_text(message.get("content"))
                    if text:
                        output.append(_Message(session_id, str(data.get("id") or line_number), role,
                                               text, self._timestamp(data.get("timestamp")),
                                               str(item), sequence))
        return output

    def _hermes_messages(self, source, prior):
        path = Path(source.path)
        if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024 * 1024:
            raise SessionImportError("unsafe Hermes SQLite source")
        connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            rows = connection.execute(
                "SELECT id,session_id,role,content,timestamp FROM messages "
                "WHERE id>? AND role IN ('user','assistant') AND content IS NOT NULL "
                "ORDER BY id LIMIT ?", (prior, self.max_batch * 2)).fetchall()
        finally:
            connection.close()
        return [_Message(str(session), str(identifier), role, text, self._timestamp(timestamp),
                         str(path), int(identifier))
                for identifier, session, role, text, timestamp in rows]

    @staticmethod
    def _content_text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(str(item.get("text", "")) for item in content
                              if isinstance(item, dict) and item.get("type") == "text")
        return ""

    @staticmethod
    def _timestamp(value):
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value) / 1000 if value > 100_000_000_000 else float(value)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
        return None

    @staticmethod
    def _source_key(source):
        return sha256(f"{source.agent}\0{source.format}\0{source.path}".encode()).hexdigest()

    def _load_checkpoints(self):
        if not self.checkpoint_path.exists():
            return {}
        data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not all(isinstance(key, str) and type(value) is int and value >= 0
                                                 for key, value in data.items()):
            raise SessionImportError("invalid importer checkpoint file")
        return data

    def _save_checkpoints(self, checkpoints):
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=self.checkpoint_path.parent, prefix=".import-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(checkpoints, stream, sort_keys=True)
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.checkpoint_path)
        finally:
            Path(temporary).unlink(missing_ok=True)


__all__ = ["ImportReport", "SessionImportError", "SessionSource", "SiblingSessionImporter",
           "SUPPORTED_AGENTS", "SUPPORTED_FORMATS"]
