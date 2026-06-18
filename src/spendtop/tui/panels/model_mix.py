from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class ModelMixPanel(Widget):
    """Bar chart of spend share by model."""

    data: reactive[dict[str, float]] = reactive({}, recompose=True)

    DEFAULT_CSS = """
    ModelMixPanel {
        height: auto;
        border: solid $primary;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]Model Mix[/bold]")
        if not self.data:
            yield Static("[dim]No data[/dim]")
            return
        total = sum(self.data.values()) or 1.0
        for model, cost in sorted(self.data.items(), key=lambda x: -x[1])[:10]:
            pct = cost / total
            bar_len = int(pct * 28)
            bar = "█" * bar_len + "░" * (28 - bar_len)
            label = (
                f"[magenta]{model:<26}[/magenta] [{bar}] [green]${cost:>8.4f}[/green] ({pct:>5.1%})"
            )
            yield Static(label)
