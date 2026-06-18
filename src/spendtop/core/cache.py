from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SpendEvent:
    ts: str  # ISO8601 UTC
    source: str  # 'anthropic' | 'openai' | ...
    cost_usd: float
    actor: str | None = None
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    raw: dict = field(default_factory=dict)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS spend_events (
    id          INTEGER PRIMARY KEY,
    ts          TEXT    NOT NULL,
    source      TEXT    NOT NULL,
    actor       TEXT,
    model       TEXT,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    cost_usd    REAL    NOT NULL,
    raw         JSON
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_spend
    ON spend_events(source, ts, COALESCE(model, ''), COALESCE(actor, ''));
"""

_DEFAULT_DB = Path.home() / ".local" / "share" / "spendtop" / "cache.db"


def _db_path() -> Path:
    return _DEFAULT_DB


@contextmanager
def _connect(path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    p = path or _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(path: Path | None = None) -> None:
    with _connect(path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def upsert_spend(events: list[SpendEvent], path: Path | None = None) -> int:
    """Insert events, ignoring duplicates. Returns the count actually inserted."""
    if not events:
        return 0
    rows = [
        (
            e.ts,
            e.source,
            e.actor,
            e.model,
            e.tokens_in,
            e.tokens_out,
            e.cost_usd,
            json.dumps(e.raw),
        )
        for e in events
    ]
    with _connect(path) as conn:
        before = conn.execute("SELECT COUNT(*) FROM spend_events").fetchone()[0]
        conn.executemany(
            """
            INSERT OR IGNORE INTO spend_events
                (ts, source, actor, model, tokens_in, tokens_out, cost_usd, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        after = conn.execute("SELECT COUNT(*) FROM spend_events").fetchone()[0]
        return after - before


def query_spend(
    since: datetime | None = None,
    source: str | None = None,
    path: Path | None = None,
) -> list[SpendEvent]:
    """Return spend events from the cache, optionally filtered by time and source."""
    clauses: list[str] = []
    params: list[object] = []
    if since:
        clauses.append("ts >= ?")
        params.append(since.isoformat())
    if source:
        clauses.append("source = ?")
        params.append(source)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    cols = "ts, source, actor, model, tokens_in, tokens_out, cost_usd, raw"
    sql = f"SELECT {cols} FROM spend_events {where} ORDER BY ts"
    with _connect(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        SpendEvent(
            ts=r["ts"],
            source=r["source"],
            actor=r["actor"],
            model=r["model"],
            tokens_in=r["tokens_in"] or 0,
            tokens_out=r["tokens_out"] or 0,
            cost_usd=r["cost_usd"],
            raw=json.loads(r["raw"]) if r["raw"] else {},
        )
        for r in rows
    ]


def latest_ts(source: str, path: Path | None = None) -> datetime | None:
    """Return the most recent event timestamp for a source, or None."""
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT MAX(ts) as max_ts FROM spend_events WHERE source = ?", (source,)
        ).fetchone()
    val = row["max_ts"] if row else None
    return datetime.fromisoformat(val) if val else None
