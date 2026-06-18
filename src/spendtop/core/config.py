from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import keyring

_CONFIG_PATH = Path.home() / ".config" / "spendtop" / "config.toml"

ConnectorStatus = Literal["ok", "disconnected", "unconfigured"]

_KEYRING_SERVICE = "spendtop"


@dataclass
class ConnectorConfig:
    enabled: bool = True
    _credential: str | None = field(default=None, repr=False, compare=False)

    def credential(self) -> str | None:
        return self._credential


@dataclass
class AppConfig:
    anthropic: ConnectorConfig = field(default_factory=ConnectorConfig)
    openai: ConnectorConfig = field(default_factory=ConnectorConfig)


def _resolve_credential(name: str, env_var: str) -> str | None:
    """Try keyring first, then env var. Never writes to disk."""
    try:
        secret = keyring.get_password(_KEYRING_SERVICE, name)
        if secret:
            return secret
    except Exception:
        pass
    return os.environ.get(env_var) or None


def store_credential(name: str, secret: str) -> None:
    keyring.set_password(_KEYRING_SERVICE, name, secret)


def load_config(path: Path | None = None) -> AppConfig:
    p = path or _CONFIG_PATH
    raw: dict = {}
    if p.exists():
        with open(p, "rb") as f:
            raw = tomllib.load(f)

    connectors = raw.get("connectors", {})

    def _cc(key: str, env_var: str) -> ConnectorConfig:
        section = connectors.get(key, {})
        enabled = bool(section.get("enabled", True))
        cred = _resolve_credential(key, env_var)
        return ConnectorConfig(enabled=enabled, _credential=cred)

    return AppConfig(
        anthropic=_cc("anthropic", "ANTHROPIC_ADMIN_KEY"),
        openai=_cc("openai", "OPENAI_ADMIN_KEY"),
    )


def ensure_config_dir(path: Path | None = None) -> None:
    p = (path or _CONFIG_PATH).parent
    p.mkdir(parents=True, exist_ok=True)
