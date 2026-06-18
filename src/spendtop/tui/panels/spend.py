from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class SpendBySourcePanel(Widget):
    """Horizontal bar chart of spend by source (tool)."""

    data: reactive[dict[str, float]] = reactive({}, recompose=True)

    DEFAULT_CSS = """
    SpendBySourcePanel {
        height: auto;
        border: solid $primary;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        total = sum(self.data.values()) or 1.0
        yield Static("[bold]Spend by Tool[/bold]")
        if not self.data:
            yield Static("[dim]No data[/dim]")
            return
        for source, cost in sorted(self.data.items(), key=lambda x: -x[1]):
            pct = cost / total
            bar_len = int(pct * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            label = f"[cyan]{source:<12}[/cyan] [{bar}] [green]${cost:>8.4f}[/green] ({pct:>5.1%})"
            yield Static(label)
