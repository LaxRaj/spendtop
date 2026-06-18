# spendtop

> A local-first terminal dashboard that shows what your AI coding tools actually cost — and ties that spend to the code your team ships.

<!-- asciinema demo GIF — record before launch and replace this comment -->

```
uvx spendtop
```

---

**Local-first. Your keys. Nothing leaves your machine.**
spendtop reads directly from Anthropic and OpenAI's admin APIs using credentials you provide, stores everything in a local SQLite cache (`~/.local/share/spendtop/cache.db`), and never phones home. No account, no SaaS, no telemetry.

---

## Quick start

```bash
# 1. Install and run (no pip install needed if you have uv)
uvx spendtop

# 2. Connect your Anthropic admin key (stored in OS keyring, never on disk)
spendtop connect anthropic

# 3. Connect your OpenAI admin key
spendtop connect openai

# 4. Launch the dashboard (auto-pulls if cache is stale)
spendtop
```

Prefer environment variables? Set `ANTHROPIC_ADMIN_KEY` and `OPENAI_ADMIN_KEY` — spendtop will pick them up automatically, no keyring needed.

> **Note:** These must be **Admin** keys, not regular API keys.
> - Anthropic: Console → Settings → Admin Keys → Create (`sk-ant-admin01-…`)
> - OpenAI: platform.openai.com → Organization → Admin API Keys (`sk-admin-…`)

---

## What you see

Three panels, always readable in a standard terminal:

| Panel | What it shows |
|---|---|
| **Spend by tool** | Horizontal bar chart — total cost per provider |
| **Daily spend** | Today's number + Unicode sparkline + 30-day projection |
| **Model mix** | Spend share by model, top 10 |

**Keybinds:** `[r]` refresh from API · `[t]` cycle timeframe (7 / 14 / 30 / 90 days) · `[e]` export to CSV · `[q]` quit

Pull without launching the TUI:

```bash
spendtop pull           # last 30 days
spendtop pull --days 7  # last 7 days
```

---

## Connectors

| Connector | Status | Env var |
|---|---|---|
| Anthropic | ✅ v0.1 | `ANTHROPIC_ADMIN_KEY` |
| OpenAI | ✅ v0.1 | `OPENAI_ADMIN_KEY` |
| Cursor | 🔜 v0.3 | — |
| GitHub Copilot | 🔜 v0.3 | — |

A broken or unconfigured connector shows `○` in the header and never crashes the dashboard — the other connectors keep running.

---

## Adding a connector

Adding one is ~80 lines. Implement the `SpendConnector` ABC from [`src/spendtop/connectors/base.py`](src/spendtop/connectors/base.py):

```python
class SpendConnector(ABC):
    name: str

    @abstractmethod
    async def pull(self, since: datetime) -> list[SpendEvent]: ...

    def status(self) -> Literal["ok", "disconnected", "unconfigured"]: ...
```

See [`src/spendtop/connectors/spend/anthropic.py`](src/spendtop/connectors/spend/anthropic.py) for a complete reference implementation — it handles pagination, 401/429 errors, and merges two API endpoints into normalized `SpendEvent` objects.

PRs for new connectors are very welcome.

---

## Coming in v0.2 — cost per merged PR

<!-- cost-per-PR screenshot — add after v0.2 ships -->

The number engineering managers actually want: **`$/merged PR` per team**, flagged against the org median. spendtop will join AI spend to your GitHub PR history and show which teams are getting the most (and least) out of their AI budget — without sending any code or PR data anywhere.

---

## Requirements

- Python 3.12+
- macOS or Linux (Windows: OS keyring may need additional configuration)
- Admin API keys for the providers you want to track

---

## License

[MIT](LICENSE)
