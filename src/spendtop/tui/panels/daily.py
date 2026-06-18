from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

_SPARKS = " ▁▂▃▄▅▆▇█"


def _sparkline(values: list[float]) -> str:
    if not values:
        return ""
    max_v = max(values) or 1.0
    return "".join(_SPARKS[min(8, int(v / max_v * 8))] for v in values)


class DailySpendPanel(Widget):
    """Big number + Unicode sparkline + 30-day projection."""

    data: reactive[dict[str, float]] = reactive({}, recompose=True)
    window: reactive[int] = reactive(30)

    DEFAULT_CSS = """
    DailySpendPanel {
        height: auto;
        border: solid $primary;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]Daily Spend[/bold]")
        if not self.data:
            yield Static("[dim]No data[/dim]")
            return
        sorted_days = sorted(self.data)[-self.window :]
        values = [self.data[d] for d in sorted_days]
        total_today = values[-1] if values else 0.0
        spark = _sparkline(values)
        avg = sum(values) / len(values) if values else 0.0
        projection = avg * 30
        yield Static(f"[bold green]${total_today:>10.4f}[/bold green]  today")
        yield Static(f"[cyan]{spark}[/cyan]  ({len(values)} days)")
        yield Static(f"[dim]30-day projection: ~${projection:.2f}[/dim]")
