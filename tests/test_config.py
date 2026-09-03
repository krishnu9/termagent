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


def test_load_config_auto_approve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = load_config(tmp_path, auto_approve=True)
    assert cfg.auto_approve is True
    cfg_default = load_config(tmp_path)
    assert cfg_default.auto_approve is False


def test_yes_flag_passes_auto_approve(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import sys

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured: dict[str, object] = {}

    def fake_run(config: object) -> None:
        captured["config"] = config

    monkeypatch.setattr("termagent.tui.run_app", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["termagent", "--yes", "--workspace", str(tmp_path)],
    )
    from termagent.__main__ import main

    main()
    assert getattr(captured["config"], "auto_approve") is True
