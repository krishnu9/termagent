from pathlib import Path

from termagent.config import Config
from termagent.tools import AgentDeps
from termagent.tui import PermissionScreen, TermagentApp, run_app


def test_app_class_exists() -> None:
    assert TermagentApp is not None
    assert callable(run_app)
    assert PermissionScreen is not None


class _StubSession:
    def __init__(self, workspace: Path, *, fail: bool = False) -> None:
        self.deps = AgentDeps(workspace=workspace)
        self.history: list[object] = ["kept"]
        self.fail = fail

    def reset(self) -> None:
        self.history = []

    async def run_stream(self, prompt: str, on_text=None) -> str:
        if self.fail:
            raise RuntimeError("api down")
        for text in ("Hel", "Hello"):
            if on_text is not None:
                on_text(text)
        return "Hello"


def _config(tmp_path: Path) -> Config:
    return Config(api_key="test-key", model="fake", workspace=tmp_path)


async def test_tui_streams_agent_text_into_transcript(tmp_path: Path) -> None:
    session = _StubSession(tmp_path)
    app = TermagentApp(session, _config(tmp_path))
    async with app.run_test() as pilot:
        await pilot.click(app.query_one("#prompt"))
        await pilot.press("h", "i", "enter")
        await pilot.pause()
        assert any(line == "agent: Hello" for line in app.transcript)
        assert any(line.startswith("you:") for line in app.transcript)
        assert app.query_one("#prompt").disabled is False


async def test_tui_error_reenables_input_and_keeps_history(tmp_path: Path) -> None:
    session = _StubSession(tmp_path, fail=True)
    app = TermagentApp(session, _config(tmp_path))
    async with app.run_test() as pilot:
        await pilot.click(app.query_one("#prompt"))
        await pilot.press("h", "i", "enter")
        await pilot.pause()
        assert any(line.startswith("error:") for line in app.transcript)
        assert app.query_one("#prompt").disabled is False
        assert session.history == ["kept"]
