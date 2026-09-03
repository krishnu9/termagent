from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ConfigError(SystemExit):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Config:
    api_key: str
    model: str
    workspace: Path
    base_url: str | None = None
    auto_approve: bool = False


def _infer_base_url(api_key: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit.rstrip("/")
    if api_key.startswith("sk-or-"):
        return OPENROUTER_BASE_URL
    return None


def load_config(
    workspace: Path | None = None, *, auto_approve: bool = False
) -> Config:
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get(
        "OPENROUTER_API_KEY", ""
    ).strip()
    if not api_key:
        raise ConfigError("OPENAI_API_KEY is not set")
    model = os.environ.get("AGENT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    explicit = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    root = (workspace if workspace is not None else Path.cwd()).resolve()
    if workspace is not None:
        if root.exists() and not root.is_dir():
            raise ConfigError(f"workspace {root} exists and is not a directory")
        root.mkdir(parents=True, exist_ok=True)
    return Config(
        api_key=api_key,
        model=model,
        workspace=root,
        base_url=_infer_base_url(api_key, explicit),
        auto_approve=auto_approve,
    )
