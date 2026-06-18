from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static

from spendtop import __version__
from spendtop.connectors.base import SpendConnector
from spendtop.core.cache import SpendEvent, init_db, query_spend, upsert_spend
from spendtop.core.metrics import spend_by_day, spend_by_model, spend_by_source
from spendtop.tui.panels.daily import DailySpendPanel
from spendtop.tui.panels.model_mix import ModelMixPanel
from spendtop.tui.panels.spend import SpendBySourcePanel

_EXPORT_PATH = Path.home() / "spendtop_export.csv"


class SpendTopApp(App):
    """spendtop — local-first TUI for AI coding tool spend."""

    TITLE = f"spendtop {__version__}"
    SUB_TITLE = "local-first · your keys · nothing leaves your machine"

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("t", "toggle_window", "Timeframe"),
        Binding("e", "export_csv", "Export CSV"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        background: $surface;
        layout: vertical;
    }
    #status-bar {
        height: 1;
        background: $panel;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, connectors: list[SpendConnector], db_path: Path | None = None) -> None:
        super().__init__()
        self._connectors = connectors
        self._db_path = db_path
        self._window_days = 30

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._status_line(), id="status-bar")
        yield SpendBySourcePanel(id="panel-source")
        yield DailySpendPanel(id="panel-daily")
        yield ModelMixPanel(id="panel-model")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_panels()

    def _status_line(self) -> str:
        parts = []
        for c in self._connectors:
            led = "●" if c.status() == "ok" else "○"
            color = "green" if c.status() == "ok" else "red"
            parts.append(f"[{color}]{led}[/{color}] {c.name}")
        return "  ".join(parts) + f"   [dim]window: {self._window_days}d[/dim]"

    def _load_events(self) -> list[SpendEvent]:
        since = datetime.now(tz=UTC) - timedelta(days=self._window_days * 2)
        return query_spend(since=since, path=self._db_path)

    def _refresh_panels(self) -> None:
        events = self._load_events()
        # Filter to current window for display
        cutoff = datetime.now(tz=UTC) - timedelta(days=self._window_days)
        window_events = [
            e for e in events if datetime.fromisoformat(e.ts.replace("Z", "+00:00")) >= cutoff
        ]

        self.query_one("#panel-source", SpendBySourcePanel).data = spend_by_source(window_events)
        self.query_one("#panel-daily", DailySpendPanel).data = spend_by_day(window_events)
        self.query_one("#panel-model", ModelMixPanel).data = spend_by_model(window_events)
        self.query_one("#status-bar", Static).update(self._status_line())

    async def action_refresh(self) -> None:
        """Pull fresh data from all configured connectors then redisplay."""
        since = datetime.now(tz=UTC) - timedelta(days=self._window_days)
        for connector in self._connectors:
            try:
                new_events = await connector.pull(since)
                if new_events:
                    init_db(self._db_path)
                    upsert_spend(new_events, self._db_path)
            except Exception:
                pass
        self._refresh_panels()
        self.notify("Refreshed")

    def action_toggle_window(self) -> None:
        """Cycle through timeframes: 7 → 14 → 30 → 90 days."""
        cycle = [7, 14, 30, 90]
        idx = cycle.index(self._window_days) if self._window_days in cycle else 0
        self._window_days = cycle[(idx + 1) % len(cycle)]
        self._refresh_panels()
        self.notify(f"Timeframe: {self._window_days}d")

    def action_export_csv(self) -> None:
        """Export visible events to ~/spendtop_export.csv."""
        events = self._load_events()
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["ts", "source", "actor", "model", "tokens_in", "tokens_out", "cost_usd"],
        )
        writer.writeheader()
        for e in events:
            writer.writerow(
                {
                    "ts": e.ts,
                    "source": e.source,
                    "actor": e.actor,
                    "model": e.model,
                    "tokens_in": e.tokens_in,
                    "tokens_out": e.tokens_out,
                    "cost_usd": e.cost_usd,
                }
            )
        _EXPORT_PATH.write_text(buf.getvalue())
        self.notify(f"Exported to {_EXPORT_PATH}")
