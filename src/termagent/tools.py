from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import RunContext

from termagent.sandbox import SandboxError, resolve_in_workspace

SHELL_TIMEOUT = 30


ApproveFn = Callable[[str, dict[str, object]], bool]
GATED_TOOLS = frozenset({"write_file", "run_shell"})


@dataclass
class AgentDeps:
    workspace: Path
    on_tool: Callable[[str, dict[str, object]], None] | None = field(default=None)
    approve: ApproveFn | None = field(default=None)
    auto_approve: bool = False


def _notify(ctx: RunContext[AgentDeps], name: str, args: dict[str, object]) -> None:
    if ctx.deps.on_tool is not None:
        ctx.deps.on_tool(name, args)


def _error(exc: BaseException | str) -> str:
    return f"error: {exc}"


def _allowed(ctx: RunContext[AgentDeps], name: str, args: dict[str, object]) -> bool:
    if name not in GATED_TOOLS:
        return True
    if ctx.deps.auto_approve:
        return True
    if ctx.deps.approve is None:
        return False
    return bool(ctx.deps.approve(name, args))


def read_file(ctx: RunContext[AgentDeps], path: str) -> str:
    """Read a UTF-8 text file inside the workspace."""
    _notify(ctx, "read_file", {"path": path})
    try:
        target = resolve_in_workspace(ctx.deps.workspace, path)
        return target.read_text(encoding="utf-8")
    except (SandboxError, OSError, UnicodeDecodeError) as exc:
        return _error(exc)


def write_file(ctx: RunContext[AgentDeps], path: str, content: str) -> str:
    """Create or overwrite a UTF-8 text file inside the workspace."""
    args: dict[str, object] = {"path": path}
    _notify(ctx, "write_file", args)
    if not _allowed(ctx, "write_file", {**args, "content": content}):
        return _error("user denied write_file")
    try:
        target = resolve_in_workspace(ctx.deps.workspace, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {target.relative_to(ctx.deps.workspace.resolve())}"
    except (SandboxError, OSError) as exc:
        return _error(exc)


def list_dir(ctx: RunContext[AgentDeps], path: str) -> str:
    """List a directory inside the workspace. Each line is 'file' or 'dir' plus the name."""
    _notify(ctx, "list_dir", {"path": path})
    try:
        target = resolve_in_workspace(ctx.deps.workspace, path)
        if not target.is_dir():
            return _error(NotADirectoryError(f"{path} is not a directory"))
        lines: list[str] = []
        for entry in sorted(target.iterdir(), key=lambda p: p.name):
            kind = "dir" if entry.is_dir() else "file"
            lines.append(f"{kind} {entry.name}")
        return "\n".join(lines) if lines else "(empty)"
    except (SandboxError, OSError) as exc:
        return _error(exc)


def run_shell(ctx: RunContext[AgentDeps], command: str) -> str:
    """Run a shell command with cwd set to the workspace. Timeout is SHELL_TIMEOUT seconds."""
    args: dict[str, object] = {"command": command}
    _notify(ctx, "run_shell", args)
    if not _allowed(ctx, "run_shell", args):
        return _error("user denied run_shell")
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=ctx.deps.workspace.resolve(),
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return (
            f"exit_code={completed.returncode}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
    except subprocess.TimeoutExpired as exc:
        return _error(f"timeout after {SHELL_TIMEOUT}s: {exc}")
    except OSError as exc:
        return _error(exc)
