from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from spendtop.core.cache import SpendEvent


def spend_by_source(events: list[SpendEvent]) -> dict[str, float]:
    """Total cost_usd grouped by source."""
    result: dict[str, float] = defaultdict(float)
    for e in events:
        result[e.source] += e.cost_usd
    return dict(result)


def spend_by_model(events: list[SpendEvent]) -> dict[str, float]:
    """Total cost_usd grouped by model (None model → '_unknown')."""
    result: dict[str, float] = defaultdict(float)
    for e in events:
        key = e.model or "_unknown"
        result[key] += e.cost_usd
    return dict(result)


def spend_by_day(events: list[SpendEvent]) -> dict[str, float]:
    """Total cost_usd grouped by ISO date (YYYY-MM-DD, UTC)."""
    result: dict[str, float] = defaultdict(float)
    for e in events:
        day = e.ts[:10]  # ISO8601 → first 10 chars = YYYY-MM-DD
        result[day] += e.cost_usd
    return dict(result)


def total_and_delta(
    events: list[SpendEvent],
    window: int = 30,
) -> tuple[float, float]:
    """
    Return (total_usd_in_window, delta_vs_prior_window).

    `window` is in days. Compares current window [now-window, now) against
    prior window [now-2*window, now-window).
    """
    now = datetime.now(tz=UTC)
    cutoff_current = now - timedelta(days=window)
    cutoff_prior = now - timedelta(days=2 * window)

    current = 0.0
    prior = 0.0
    for e in events:
        try:
            ts = datetime.fromisoformat(e.ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts >= cutoff_current:
            current += e.cost_usd
        elif ts >= cutoff_prior:
            prior += e.cost_usd

    delta = current - prior
    return current, delta
