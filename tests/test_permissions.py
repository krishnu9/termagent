from pathlib import Path

from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from termagent.tools import AgentDeps, list_dir, read_file, run_shell, write_file


def _ctx(
    workspace: Path,
    *,
    approve=None,
    auto_approve: bool = False,
) -> RunContext[AgentDeps]:
    return RunContext(
        deps=AgentDeps(
            workspace=workspace,
            approve=approve,
            auto_approve=auto_approve,
        ),
        model=TestModel(),
        usage=RunUsage(),
        tool_name="test",
    )


def test_write_file_denied_does_not_write(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, approve=lambda name, args: False)
    result = write_file(ctx, "secret.txt", "nope")
    assert result.startswith("error:")
    assert "denied" in result.lower()
    assert "write_file" in result
    assert not (tmp_path / "secret.txt").exists()


def test_write_file_approved_writes(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, approve=lambda name, args: True)
    result = write_file(ctx, "ok.txt", "yes")
    assert "wrote" in result.lower()
    assert (tmp_path / "ok.txt").read_text() == "yes"


def test_run_shell_denied_does_not_run(tmp_path: Path) -> None:
    marker = tmp_path / "ran.txt"
    ctx = _ctx(tmp_path, approve=lambda name, args: False)
    result = run_shell(ctx, "touch ran.txt")
    assert result.startswith("error:")
    assert "denied" in result.lower()
    assert "run_shell" in result
    assert not marker.exists()


def test_run_shell_approved_runs(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, approve=lambda name, args: True)
    result = run_shell(ctx, "echo hello")
    assert "exit_code=0" in result
    assert "hello" in result


def test_read_and_list_skip_approver(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hi")
    called: list[str] = []

    def approve(name: str, args: dict[str, object]) -> bool:
        called.append(name)
        return False

    ctx = _ctx(tmp_path, approve=approve)
    assert read_file(ctx, "a.txt") == "hi"
    assert "a.txt" in list_dir(ctx, ".")
    assert called == []


def test_auto_approve_skips_callback(tmp_path: Path) -> None:
    called: list[str] = []

    def approve(name: str, args: dict[str, object]) -> bool:
        called.append(name)
        return False

    ctx = _ctx(tmp_path, approve=approve, auto_approve=True)
    write_file(ctx, "x.txt", "ok")
    run_shell(ctx, "true")
    assert called == []
    assert (tmp_path / "x.txt").read_text() == "ok"
