"""Persistent, local state for voice-facing global autonomy controls.

This module deliberately records control intent only. A runtime may consult
``AutonomyState.can_run`` before starting work and observe ``stop_all`` to
cancel active work; this controller does not launch or stop agents itself.
"""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class AutonomyState:
    """Immutable snapshot of the system-wide autonomy control state."""

    paused: bool
    stop_all: bool
    revision: int
    updated_at: float

    @property
    def can_run(self) -> bool:
        """Whether new autonomous work may be started."""

        return not self.paused and not self.stop_all


class AutonomyControl:
    """Persist idempotent pause, resume, and stop-all commands in SQLite.

    The caller chooses the database path so this standalone controller does
    not assume where Jarvis keeps its private state. The database is created
    with owner-only permissions when the filesystem supports POSIX modes.
    """

    def __init__(self, database_path: str | os.PathLike[str], *, clock: Callable[[], float] = time.time):
        self.database_path = Path(database_path).expanduser().absolute()
        self._clock = clock
        self.database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._initialize()

    def get_state(self) -> AutonomyState:
        """Return the latest persisted state."""

        with self._session() as connection:
            row = connection.execute(
                "SELECT paused, stop_all, revision, updated_at FROM autonomy_control WHERE id = 1"
            ).fetchone()
        assert row is not None
        return AutonomyState(bool(row[0]), bool(row[1]), int(row[2]), float(row[3]))

    def pause(self) -> AutonomyState:
        """Pause autonomous work; repeated calls leave the state unchanged."""

        return self._set(paused=True)

    def resume(self) -> AutonomyState:
        """Resume autonomy and clear a prior stop-all latch."""

        return self._set(paused=False, stop_all=False)

    def stop_all(self) -> AutonomyState:
        """Latch a global stop request for runtimes to observe."""

        return self._set(paused=False, stop_all=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10.0)
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        self._secure_permissions()
        return connection

    def _initialize(self) -> None:
        with self._session() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS autonomy_control (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    paused INTEGER NOT NULL CHECK (paused IN (0, 1)),
                    stop_all INTEGER NOT NULL CHECK (stop_all IN (0, 1)),
                    revision INTEGER NOT NULL CHECK (revision >= 0),
                    updated_at REAL NOT NULL
                )"""
            )
            connection.execute(
                "INSERT OR IGNORE INTO autonomy_control "
                "(id, paused, stop_all, revision, updated_at) VALUES (1, 0, 0, 0, ?)",
                (self._clock(),),
            )

    def _set(self, *, paused: bool | None = None, stop_all: bool | None = None) -> AutonomyState:
        with self._session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT paused, stop_all, revision, updated_at FROM autonomy_control WHERE id = 1"
            ).fetchone()
            assert row is not None
            next_paused = bool(row[0]) if paused is None else paused
            next_stop_all = bool(row[1]) if stop_all is None else stop_all
            if next_paused != bool(row[0]) or next_stop_all != bool(row[1]):
                updated_at = self._clock()
                connection.execute(
                    "UPDATE autonomy_control SET paused = ?, stop_all = ?, revision = ?, updated_at = ? WHERE id = 1",
                    (int(next_paused), int(next_stop_all), int(row[2]) + 1, updated_at),
                )
                row = (next_paused, next_stop_all, int(row[2]) + 1, updated_at)
            connection.commit()
        self._secure_permissions()
        return AutonomyState(bool(row[0]), bool(row[1]), int(row[2]), float(row[3]))

    @contextmanager
    def _session(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _secure_permissions(self) -> None:
        """Restrict the database and SQLite sidecars to the current user."""

        for path in (self.database_path, Path(f"{self.database_path}-journal")):
            try:
                path.chmod(0o600)
            except FileNotFoundError:
                pass

