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


def test_missing_workspace_dir_is_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    missing = tmp_path / "new-project"
    assert not missing.exists()
    cfg = load_config(missing)
    assert missing.is_dir()
    assert cfg.workspace == missing.resolve()


def test_existing_workspace_dir_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    existing = tmp_path / "repo"
    existing.mkdir()
    marker = existing / "keep-me.txt"
    marker.write_text("ok", encoding="utf-8")
    cfg = load_config(existing)
    assert cfg.workspace == existing.resolve()
    assert marker.read_text(encoding="utf-8") == "ok"
    assert list(existing.iterdir()) == [marker]


def test_workspace_path_that_is_a_file_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("nope", encoding="utf-8")
    with pytest.raises(ConfigError, match="not a directory"):
        load_config(file_path)
