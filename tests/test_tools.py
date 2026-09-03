import time
from pathlib import Path

from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from termagent.tools import (
    AgentDeps,
    list_dir,
    read_file,
    run_shell,
    search_text,
    write_file,
)


def _ctx(workspace: Path) -> RunContext[AgentDeps]:
    return RunContext(
        deps=AgentDeps(workspace=workspace),
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


def test_list_dir_hides_node_modules(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    (tmp_path / "keep.py").write_text("ok", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("secret", encoding="utf-8")
    listing = list_dir(ctx, ".")
    assert "keep.py" in listing
    assert "node_modules" not in listing


def test_read_file_truncates_large_content(tmp_path: Path, monkeypatch: object) -> None:
    import termagent.tools as tools

    monkeypatch.setattr(tools, "READ_FILE_MAX_CHARS", 20)
    ctx = _ctx(tmp_path)
    (tmp_path / "big.txt").write_text("abcdefghijklmnopqrstuvwxyz", encoding="utf-8")
    result = read_file(ctx, "big.txt")
    assert "truncated" in result.lower()
    assert "20" in result
    assert "abcdefghijklmnopqrstuvwxyz" not in result
    assert "abcdefghijklmnopqrst" in result


def test_search_text_finds_match_and_skips_junk_dirs(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("UNIQUE_TOKEN_XYZ = 1\n", encoding="utf-8")
    git_dir = tmp_path / ".git" / "objects"
    git_dir.mkdir(parents=True)
    (git_dir / "pack").write_text("UNIQUE_TOKEN_XYZ in git\n", encoding="utf-8")
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("UNIQUE_TOKEN_XYZ in node_modules\n", encoding="utf-8")
    result = search_text(ctx, "UNIQUE_TOKEN_XYZ")
    assert "src/app.py" in result.replace("\\", "/")
    assert "UNIQUE_TOKEN_XYZ = 1" in result
    assert "node_modules" not in result
    assert ".git" not in result


def test_run_shell_timeout(tmp_path: Path, monkeypatch: object) -> None:
    import termagent.tools as tools

    monkeypatch.setattr(tools, "SHELL_TIMEOUT", 0.1)
    started = time.monotonic()
    result = run_shell(_ctx(tmp_path), "sleep 5")
    elapsed = time.monotonic() - started
    assert elapsed < 3
    assert result.startswith("error:")
    assert "timeout" in result.lower()
