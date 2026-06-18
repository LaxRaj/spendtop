"""Unit tests for core/metrics.py — pure functions over fixed event fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from spendtop.core.cache import SpendEvent
from spendtop.core.metrics import (
    spend_by_day,
    spend_by_model,
    spend_by_source,
    total_and_delta,
)

_NOW = datetime.now(tz=UTC)


def _event(
    source: str = "anthropic",
    cost: float = 1.0,
    model: str | None = "claude-3",
    days_ago: int = 0,
) -> SpendEvent:
    ts = (_NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
    return SpendEvent(ts=ts, source=source, model=model, cost_usd=cost)


_FIXTURES = [
    _event("anthropic", 1.0, "claude-opus-4", days_ago=1),
    _event("anthropic", 2.0, "claude-sonnet-4", days_ago=1),
    _event("openai", 0.5, "gpt-4o", days_ago=1),
    _event("openai", 0.3, "gpt-4o", days_ago=2),
    _event("anthropic", 1.5, "claude-opus-4", days_ago=40),  # outside 30-day window
]


def test_spend_by_source():
    result = spend_by_source(_FIXTURES)
    assert result["anthropic"] == pytest.approx(1.0 + 2.0 + 1.5)
    assert result["openai"] == pytest.approx(0.5 + 0.3)


def test_spend_by_model():
    result = spend_by_model(_FIXTURES)
    assert result["claude-opus-4"] == pytest.approx(1.0 + 1.5)
    assert result["claude-sonnet-4"] == pytest.approx(2.0)
    assert result["gpt-4o"] == pytest.approx(0.5 + 0.3)


def test_spend_by_model_none_model():
    events = [_event(model=None, cost=9.9)]
    assert spend_by_model(events)["_unknown"] == pytest.approx(9.9)


def test_spend_by_day():
    result = spend_by_day(_FIXTURES)
    assert len(result) <= len(_FIXTURES)  # some days may merge
    total = sum(result.values())
    assert total == pytest.approx(sum(e.cost_usd for e in _FIXTURES))


def test_total_and_delta_window():
    total, delta = total_and_delta(_FIXTURES, window=30)
    # only events within 30 days: 1.0 + 2.0 + 0.5 + 0.3 = 3.8
    assert total == pytest.approx(3.8)
    # prior 30-day window: 1.5 (the 40-days-ago event)
    assert delta == pytest.approx(3.8 - 1.5)


def test_total_and_delta_empty():
    total, delta = total_and_delta([])
    assert total == 0.0
    assert delta == 0.0


def test_spend_by_source_empty():
    assert spend_by_source([]) == {}


def test_spend_by_model_empty():
    assert spend_by_model([]) == {}


def test_spend_by_day_empty():
    assert spend_by_day([]) == {}
