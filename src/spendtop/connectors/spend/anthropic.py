from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from spendtop.connectors.base import ConnectorStatus, SpendConnector
from spendtop.core.cache import SpendEvent

log = logging.getLogger(__name__)

_BASE = "https://api.anthropic.com"
_VERSION = "2023-06-01"
# Default pull window: 30 days back, max bucket=1d
_MAX_DAYS = 31


class AnthropicConnector(SpendConnector):
    name = "anthropic"

    def __init__(self, api_key: str | None) -> None:
        self._key = api_key
        self._last_error: str | None = None

    def status(self) -> ConnectorStatus:
        if not self._key:
            return "unconfigured"
        if self._last_error:
            return "disconnected"
        return "ok"

    async def pull(self, since: datetime) -> list[SpendEvent]:
        if not self._key:
            return []
        try:
            events = await self._fetch(since)
            self._last_error = None
            return events
        except Exception as exc:
            self._last_error = str(exc)
            log.warning("anthropic connector error: %s", exc)
            return []

    async def _fetch(self, since: datetime) -> list[SpendEvent]:
        now = datetime.now(tz=UTC)
        starting_at = since.astimezone(UTC).isoformat().replace("+00:00", "Z")
        ending_at = now.isoformat().replace("+00:00", "Z")

        headers = {
            "x-api-key": self._key,
            "anthropic-version": _VERSION,
        }

        async with httpx.AsyncClient(base_url=_BASE, headers=headers, timeout=30) as client:
            costs = await self._paginate_costs(client, starting_at, ending_at)
            usages = await self._paginate_usage(client, starting_at, ending_at)

        return _merge_into_events(costs, usages)

    async def _paginate_costs(
        self, client: httpx.AsyncClient, starting_at: str, ending_at: str
    ) -> list[dict[str, Any]]:
        buckets: list[dict[str, Any]] = []
        page: str | None = None
        while True:
            params: dict[str, Any] = {
                "starting_at": starting_at,
                "ending_at": ending_at,
                "bucket_width": "1d",
                "group_by[]": "description",
                "limit": 31,
            }
            if page:
                params["page"] = page
            resp = await client.get("/v1/organizations/cost_report", params=params)
            _raise_for_status(resp)
            body = resp.json()
            buckets.extend(body.get("data", []))
            if not body.get("has_more"):
                break
            page = body.get("next_page")
        return buckets

    async def _paginate_usage(
        self, client: httpx.AsyncClient, starting_at: str, ending_at: str
    ) -> list[dict[str, Any]]:
        buckets: list[dict[str, Any]] = []
        page: str | None = None
        while True:
            params: dict[str, Any] = {
                "starting_at": starting_at,
                "ending_at": ending_at,
                "bucket_width": "1d",
                "group_by[]": "model",
                "limit": 31,
            }
            if page:
                params["page"] = page
            resp = await client.get("/v1/organizations/usage_report/messages", params=params)
            _raise_for_status(resp)
            body = resp.json()
            buckets.extend(body.get("data", []))
            if not body.get("has_more"):
                break
            page = body.get("next_page")
        return buckets


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise PermissionError("Anthropic: invalid or missing admin key (HTTP 401)")
    if resp.status_code == 429:
        raise RuntimeError("Anthropic: rate limited (HTTP 429)")
    resp.raise_for_status()


def _merge_into_events(
    cost_buckets: list[dict[str, Any]],
    usage_buckets: list[dict[str, Any]],
) -> list[SpendEvent]:
    """
    Cost buckets: [{starting_at, ending_at, results: [{model, amount (cents str), ...}]}]
    Usage buckets: [{starting_at, results: [{model, uncached_input_tokens, output_tokens, ...}]}]
    → one SpendEvent per (starting_at, model)
    """
    # key: (starting_at, model) → total_cost_usd
    cost_map: dict[tuple[str, str | None], float] = {}
    for bucket in cost_buckets:
        ts = bucket["starting_at"]
        for item in bucket.get("results", []):
            model = item.get("model")
            if item.get("cost_type") != "tokens":
                continue
            amount_cents = float(item.get("amount", 0))
            cost_map[(ts, model)] = cost_map.get((ts, model), 0.0) + amount_cents / 100.0

    # key: (starting_at, model) → {tokens_in, tokens_out, cache_read}
    token_map: dict[tuple[str, str | None], dict[str, int]] = {}
    for bucket in usage_buckets:
        ts = bucket["starting_at"]
        for item in bucket.get("results", []):
            model = item.get("model")
            key = (ts, model)
            if key not in token_map:
                token_map[key] = {"tokens_in": 0, "tokens_out": 0}
            token_map[key]["tokens_in"] += (item.get("uncached_input_tokens") or 0) + (
                item.get("cache_read_input_tokens") or 0
            )
            token_map[key]["tokens_out"] += item.get("output_tokens") or 0

    all_keys = set(cost_map) | set(token_map)
    events: list[SpendEvent] = []
    for ts, model in sorted(all_keys):
        cost = cost_map.get((ts, model), 0.0)
        toks = token_map.get((ts, model), {})
        events.append(
            SpendEvent(
                ts=ts,
                source="anthropic",
                model=model,
                cost_usd=cost,
                tokens_in=toks.get("tokens_in", 0),
                tokens_out=toks.get("tokens_out", 0),
                raw={"source_api": "cost_report+usage_report"},
            )
        )
    return events
