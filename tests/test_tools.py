import time
from pathlib import Path

from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from termagent.tools import AgentDeps, list_dir, read_file, run_shell, write_file


def _ctx(workspace: Path) -> RunContext[AgentDeps]:
    return RunContext(
        deps=AgentDeps(workspace=workspace, auto_approve=True),
        model=TestModel(),
        usage=RunUsage(),
        tool_name="test",
    )


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    assert "wrote" in write_file(ctx, "notes.txt", "hello").lower()
    assert read_file(ctx, "notes.txt") == "hello"


def test_list_dir_sees_written_file(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    write_file(ctx, "notes.txt", "hello")
    listing = list_dir(ctx, ".")
    assert "notes.txt" in listing


def test_read_escape_returns_error(tmp_path: Path) -> None:
    result = read_file(_ctx(tmp_path), "../etc/passwd")
    assert result.startswith("error:")
    assert "workspace" in result.lower()


def test_run_shell_cwd_is_workspace(tmp_path: Path) -> None:
    (tmp_path / "marker.txt").write_text("x")
    result = run_shell(_ctx(tmp_path), "ls")
    assert "marker.txt" in result
    assert "exit_code=0" in result


def test_run_shell_timeout(tmp_path: Path, monkeypatch: object) -> None:
    import termagent.tools as tools

    monkeypatch.setattr(tools, "SHELL_TIMEOUT", 0.1)
    started = time.monotonic()
    result = run_shell(_ctx(tmp_path), "sleep 5")
    elapsed = time.monotonic() - started
    assert elapsed < 3
    assert result.startswith("error:")
    assert "timeout" in result.lower()
