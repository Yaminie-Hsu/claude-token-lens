"""SQLite-based session and compression event tracking."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

DATA_DIR = Path(os.environ.get("CLAUDE_TOKEN_LENS_DIR", "~/.claude-token-lens")).expanduser()
DB_PATH = DATA_DIR / "sessions.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,
    session_id      TEXT,
    original_tokens INTEGER NOT NULL,
    compressed_tokens INTEGER NOT NULL,
    saved_tokens    INTEGER NOT NULL,
    strategies      TEXT,
    cwd             TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _ensure_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _db() -> Generator[sqlite3.Connection, None, None]:
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        yield conn


def record_event(
    original_tokens: int,
    compressed_tokens: int,
    strategies: List[str],
    session_id: Optional[str] = None,
    cwd: Optional[str] = None,
) -> None:
    saved = original_tokens - compressed_tokens
    with _db() as conn:
        conn.execute(
            """INSERT INTO events
               (ts, session_id, original_tokens, compressed_tokens, saved_tokens, strategies, cwd)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                session_id,
                original_tokens,
                compressed_tokens,
                saved,
                ",".join(strategies),
                cwd,
            ),
        )


def get_stats(days: int = 30) -> dict:
    """Return aggregated statistics for the last N days."""
    with _db() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*)                AS total_events,
                SUM(original_tokens)    AS total_original,
                SUM(compressed_tokens)  AS total_compressed,
                SUM(saved_tokens)       AS total_saved,
                AVG(CASE WHEN original_tokens > 0
                    THEN CAST(saved_tokens AS REAL) / original_tokens
                    ELSE 0 END) * 100   AS avg_pct_saved
               FROM events
               WHERE ts >= datetime('now', ?)""",
            (f"-{days} days",),
        ).fetchone()

    return {
        "days": days,
        "total_events": row["total_events"] or 0,
        "total_original": row["total_original"] or 0,
        "total_compressed": row["total_compressed"] or 0,
        "total_saved": row["total_saved"] or 0,
        "avg_pct_saved": row["avg_pct_saved"] or 0.0,
    }


def get_recent_events(limit: int = 20) -> List[sqlite3.Row]:
    with _db() as conn:
        return conn.execute(
            "SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
