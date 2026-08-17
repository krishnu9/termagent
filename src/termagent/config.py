from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(SystemExit):
    """Raised when required configuration is missing."""


@dataclass(frozen=True)
class Config:
    api_key: str
    model: str
    workspace: Path


def load_config(workspace: Path | None = None) -> Config:
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ConfigError("OPENAI_API_KEY is not set")
    model = os.environ.get("AGENT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    root = (workspace if workspace is not None else Path.cwd()).resolve()
    return Config(api_key=api_key, model=model, workspace=root)
