from pathlib import Path

import pytest

from termagent.config import ConfigError, load_config


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        load_config()


def test_defaults_and_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    cfg = load_config(tmp_path)
    assert cfg.api_key == "sk-test"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.workspace == tmp_path.resolve()


def test_custom_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("AGENT_MODEL", "gpt-4o")
    cfg = load_config(tmp_path)
    assert cfg.model == "gpt-4o"
