from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from spendtop.connectors.base import ConnectorStatus, SpendConnector
from spendtop.core.cache import SpendEvent

log = logging.getLogger(__name__)

_BASE = "https://api.openai.com"

# Pattern to strip token-type suffixes from OpenAI line_item strings.
# e.g. "gpt-4o-2024-11-20 Input Tokens" → "gpt-4o-2024-11-20"
_LINE_ITEM_RE = re.compile(
    r"\s+(Input|Output|Completion|Cached|Audio|Image|Embedding)\s+", re.IGNORECASE
)


def _model_from_line_item(line_item: str | None) -> str | None:
    if not line_item:
        return None
    return _LINE_ITEM_RE.split(line_item)[0].strip() or None


class OpenAIConnector(SpendConnector):
    name = "openai"

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
            log.warning("openai connector error: %s", exc)
            return []

    async def _fetch(self, since: datetime) -> list[SpendEvent]:
        now = datetime.now(tz=UTC)
        start_ts = int(since.astimezone(UTC).timestamp())
        end_ts = int(now.timestamp())

        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(base_url=_BASE, headers=headers, timeout=30) as client:
            costs = await self._paginate_costs(client, start_ts, end_ts)
            usages = await self._paginate_usage(client, start_ts, end_ts)

        return _merge_into_events(costs, usages)

    async def _paginate_costs(
        self, client: httpx.AsyncClient, start_ts: int, end_ts: int
    ) -> list[dict[str, Any]]:
        buckets: list[dict[str, Any]] = []
        page: str | None = None
        while True:
            params: dict[str, Any] = {
                "start_time": start_ts,
                "end_time": end_ts,
                "bucket_width": "1d",
                "group_by[]": "line_item",
                "limit": 31,
            }
            if page:
                params["page"] = page
            resp = await client.get("/v1/organization/costs", params=params)
            _raise_for_status(resp)
            body = resp.json()
            buckets.extend(body.get("data", []))
            if not body.get("has_more"):
                break
            page = body.get("next_page")
        return buckets

    async def _paginate_usage(
        self, client: httpx.AsyncClient, start_ts: int, end_ts: int
    ) -> list[dict[str, Any]]:
        buckets: list[dict[str, Any]] = []
        page: str | None = None
        while True:
            params: dict[str, Any] = {
                "start_time": start_ts,
                "end_time": end_ts,
                "bucket_width": "1d",
                "group_by[]": "model",
                "limit": 31,
            }
            if page:
                params["page"] = page
            resp = await client.get("/v1/organization/usage/completions", params=params)
            _raise_for_status(resp)
            body = resp.json()
            buckets.extend(body.get("data", []))
            if not body.get("has_more"):
                break
            page = body.get("next_page")
        return buckets


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise PermissionError("OpenAI: invalid or missing admin key (HTTP 401)")
    if resp.status_code == 429:
        raise RuntimeError("OpenAI: rate limited (HTTP 429)")
    resp.raise_for_status()


def _ts_to_iso(unix_ts: int | float) -> str:
    return datetime.fromtimestamp(unix_ts, tz=UTC).isoformat().replace("+00:00", "Z")


def _merge_into_events(
    cost_buckets: list[dict[str, Any]],
    usage_buckets: list[dict[str, Any]],
) -> list[SpendEvent]:
    """
    Cost buckets: [{start_time (unix), results: [{line_item, amount.value (USD)}]}]
    Usage buckets: [{start_time (unix), results: [{model, input_tokens, output_tokens}]}]
    → one SpendEvent per (start_time_iso, model)
    """
    # key: (start_ts_iso, model) → cost_usd
    cost_map: dict[tuple[str, str | None], float] = {}
    for bucket in cost_buckets:
        ts = _ts_to_iso(bucket["start_time"])
        for item in bucket.get("results", []):
            model = _model_from_line_item(item.get("line_item"))
            amount_usd = (item.get("amount") or {}).get("value", 0.0)
            cost_map[(ts, model)] = cost_map.get((ts, model), 0.0) + float(amount_usd)

    # key: (start_ts_iso, model) → {tokens_in, tokens_out}
    token_map: dict[tuple[str, str | None], dict[str, int]] = {}
    for bucket in usage_buckets:
        ts = _ts_to_iso(bucket["start_time"])
        for item in bucket.get("results", []):
            model = item.get("model")
            key = (ts, model)
            if key not in token_map:
                token_map[key] = {"tokens_in": 0, "tokens_out": 0}
            token_map[key]["tokens_in"] += (item.get("input_tokens") or 0) + (
                item.get("input_cached_tokens") or 0
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
                source="openai",
                model=model,
                cost_usd=cost,
                tokens_in=toks.get("tokens_in", 0),
                tokens_out=toks.get("tokens_out", 0),
                raw={"source_api": "costs+usage/completions"},
            )
        )
    return events
