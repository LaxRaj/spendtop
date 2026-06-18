"""Unit tests for core/cache.py — SQLite schema + upsert/query helpers."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

from spendtop.core.cache import SpendEvent, init_db, latest_ts, query_spend, upsert_spend


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    p = tmp_path / "test_cache.db"
    init_db(p)
    return p


_E1 = SpendEvent(
    ts="2026-01-01T00:00:00Z",
    source="anthropic",
    model="claude-opus-4",
    cost_usd=1.23,
    tokens_in=1000,
    tokens_out=500,
)
_E2 = SpendEvent(
    ts="2026-01-02T00:00:00Z",
    source="openai",
    model="gpt-4o",
    cost_usd=0.45,
    tokens_in=200,
    tokens_out=100,
)


def test_upsert_and_query(db: Path):
    n = upsert_spend([_E1, _E2], db)
    assert n == 2
    events = query_spend(path=db)
    assert len(events) == 2
    assert events[0].source == "anthropic"
    assert events[1].source == "openai"


def test_upsert_idempotent(db: Path):
    upsert_spend([_E1], db)
    n = upsert_spend([_E1], db)  # duplicate → ignored
    assert n == 0
    events = query_spend(path=db)
    assert len(events) == 1


def test_query_filter_source(db: Path):
    upsert_spend([_E1, _E2], db)
    events = query_spend(source="anthropic", path=db)
    assert len(events) == 1
    assert events[0].source == "anthropic"


def test_query_filter_since(db: Path):
    upsert_spend([_E1, _E2], db)
    from datetime import datetime

    since = datetime(2026, 1, 2, tzinfo=UTC)
    events = query_spend(since=since, path=db)
    assert len(events) == 1
    assert events[0].source == "openai"


def test_latest_ts_empty(db: Path):
    assert latest_ts("anthropic", db) is None


def test_latest_ts(db: Path):
    upsert_spend([_E1, _E2], db)
    ts = latest_ts("anthropic", db)
    assert ts is not None
    assert ts.year == 2026


def test_upsert_empty(db: Path):
    assert upsert_spend([], db) == 0
