from pathlib import Path

import pytest

from termagent.config import ConfigError, load_config


def test_missing_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
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


def test_openai_key_has_no_base_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    cfg = load_config(tmp_path)
    assert cfg.base_url is None


def test_openrouter_key_sets_base_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-or-v1-abc")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("AGENT_MODEL", "z-ai/glm-5.3-flash")
    cfg = load_config(tmp_path)
    assert cfg.base_url == "https://openrouter.ai/api/v1"
    assert cfg.model == "z-ai/glm-5.3-flash"


def test_explicit_base_url_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-or-v1-abc")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
    cfg = load_config(tmp_path)
    assert cfg.base_url == "https://example.com/v1"


def test_openrouter_api_key_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-from-or")
    cfg = load_config(tmp_path)
    assert cfg.api_key == "sk-or-v1-from-or"
    assert cfg.base_url == "https://openrouter.ai/api/v1"


def test_create_chat_model_uses_openrouter_base(tmp_path: Path) -> None:
    from termagent.agent import create_chat_model
    from termagent.config import Config

    cfg = Config(
        api_key="sk-or-v1-abc",
        model="z-ai/glm-5.3-flash",
        workspace=tmp_path,
        base_url="https://openrouter.ai/api/v1",
    )
    model = create_chat_model(cfg)
    assert model.model_name == "z-ai/glm-5.3-flash"
    assert "openrouter.ai" in model.provider.base_url
