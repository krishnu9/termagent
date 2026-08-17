# termagent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Python TUI coding agent that runs a PydanticAI tool loop (read/write/list/shell) inside a workspace sandbox.

**Architecture:** Textual renders a transcript and drives one `CodingSession.run()` at a time. PydanticAI owns the model/tool loop. Tools are plain functions that take `RunContext[AgentDeps]`, resolve paths through `sandbox.resolve_in_workspace`, and return strings (never raise into the TUI). `AgentDeps.on_tool` is how the TUI sees `→ tool args` live.

**Tech Stack:** Python 3.11+, pydantic-ai (OpenAI-compatible), textual, python-dotenv, pytest, pytest-asyncio

## Global Constraints

- Package lives at `src/termagent/`; tests at `tests/`; install with `pip install -e ".[dev]"`
- Runtime deps: `pydantic-ai`, `textual`, `python-dotenv`; dev extra: `pytest`, `pytest-asyncio`
- Env: `OPENAI_API_KEY` required; `AGENT_MODEL` defaults to `gpt-4o-mini`; `--workspace` defaults to cwd
- Tools: `read_file`, `write_file`, `list_dir`, `run_shell` only; all return `str`
- Shell: `subprocess.run(..., cwd=workspace, timeout=30, shell=True)`; not a filesystem jail
- No live API in tests (`pydantic_ai.models.ALLOW_MODEL_REQUESTS = False`)
- No streaming, git, persistence, or permission prompts

## File map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Package metadata, deps, pytest config |
| `.gitignore` | venv, `__pycache__`, `.env` |
| `src/termagent/__init__.py` | Package marker |
| `src/termagent/sandbox.py` | `SandboxError`, `resolve_in_workspace` |
| `src/termagent/tools.py` | Four tools + `SHELL_TIMEOUT = 30` |
| `src/termagent/agent.py` | `AgentDeps`, `build_agent`, `CodingSession` |
| `src/termagent/config.py` | `Config`, `load_config`, `ConfigError` |
| `src/termagent/tui.py` | Textual app |
| `src/termagent/__main__.py` | argparse + start TUI |
| `tests/conftest.py` | Block live model requests |
| `tests/test_sandbox.py` | Path allow/deny |
| `tests/test_tools.py` | Round-trip, list, shell cwd, timeout |
| `tests/test_agent_loop.py` | FunctionModel: list_dir then final text |
| `tests/test_config.py` | Missing key / defaults |
| `.env.example` | Key + model placeholders |
| `README.md` | How to run |

---

### Task 1: Package skeleton + sandbox

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/termagent/__init__.py`
- Create: `src/termagent/sandbox.py`
- Create: `tests/conftest.py`
- Create: `tests/test_sandbox.py`

**Interfaces:**
- Consumes: nothing
- Produces: `class SandboxError(ValueError)` and `def resolve_in_workspace(workspace: Path, path: str) -> Path` (raises `SandboxError` if the resolved path is not inside `workspace`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/conftest.py
from pydantic_ai import models

models.ALLOW_MODEL_REQUESTS = False
```

```python
# tests/test_sandbox.py
from pathlib import Path

import pytest

from termagent.sandbox import SandboxError, resolve_in_workspace


def test_relative_file_inside_workspace(tmp_path: Path) -> None:
    resolved = resolve_in_workspace(tmp_path, "foo.txt")
    assert resolved == (tmp_path / "foo.txt").resolve()


def test_absolute_path_inside_workspace(tmp_path: Path) -> None:
    target = (tmp_path / "foo.txt").resolve()
    assert resolve_in_workspace(tmp_path, str(target)) == target


def test_parent_escape_rejected(tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="workspace"):
        resolve_in_workspace(tmp_path, "../etc/passwd")


def test_absolute_path_outside_workspace_rejected(tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="workspace"):
        resolve_in_workspace(tmp_path, "/etc/passwd")
```

- [ ] **Step 2: Add pyproject.toml and gitignore so pytest can import the package**

```toml
# pyproject.toml
[project]
name = "termagent"
version = "0.1.0"
description = "A small terminal coding agent"
requires-python = ">=3.11"
dependencies = [
    "pydantic-ai",
    "textual",
    "python-dotenv",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio"]

[project.scripts]
termagent = "termagent.__main__:main"

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

```
# .gitignore
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
.env
dist/
build/
```

Empty `src/termagent/__init__.py`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest tests/test_sandbox.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'termagent.sandbox'` (or import error for `resolve_in_workspace`)

- [ ] **Step 4: Write minimal sandbox**

```python
# src/termagent/sandbox.py
from pathlib import Path


class SandboxError(ValueError):
    """Raised when a path resolves outside the workspace."""


def resolve_in_workspace(workspace: Path, path: str) -> Path:
    root = workspace.resolve()
    candidate = Path(path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SandboxError(f"path {path!r} is outside the workspace {root}") from exc
    return resolved
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_sandbox.py -v`

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src/termagent/__init__.py src/termagent/sandbox.py tests/conftest.py tests/test_sandbox.py
git commit -m "feat: add workspace path sandbox"
```

---

### Task 2: Tools

**Files:**
- Create: `src/termagent/tools.py`
- Create: `tests/test_tools.py`

**Interfaces:**
- Consumes: `resolve_in_workspace`, `SandboxError`; `AgentDeps` is defined in `agent.py` in Task 3, so tools take a small protocol: `ctx.deps.workspace: Path` and optional `ctx.deps.on_tool`. To avoid a circular import, put `AgentDeps` in `tools.py` now (Task 3 imports it from `tools.py`).
- Produces:
  - `SHELL_TIMEOUT: int = 30`
  - `@dataclass class AgentDeps: workspace: Path; on_tool: Callable[[str, dict[str, object]], None] | None = None`
  - `def read_file(ctx: RunContext[AgentDeps], path: str) -> str`
  - `def write_file(ctx: RunContext[AgentDeps], path: str, content: str) -> str`
  - `def list_dir(ctx: RunContext[AgentDeps], path: str) -> str`
  - `def run_shell(ctx: RunContext[AgentDeps], command: str) -> str`
  - `def _notify(ctx: RunContext[AgentDeps], name: str, args: dict[str, object]) -> None`

Tools catch all exceptions and return an error string starting with `error:`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools.py
import time
from pathlib import Path

from pydantic_ai import RunContext

from termagent.tools import AgentDeps, list_dir, read_file, run_shell, write_file


def _ctx(workspace: Path) -> RunContext[AgentDeps]:
    return RunContext(
        deps=AgentDeps(workspace=workspace),
        retry=0,
        messages=[],
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
```

`RunContext` construction may differ by pydantic-ai version. If the constructor fails, use this fallback in the test helper (do not change tool signatures):

```python
def _ctx(workspace: Path) -> RunContext[AgentDeps]:
    deps = AgentDeps(workspace=workspace)
    try:
        return RunContext(deps=deps, retry=0, messages=[], tool_name="test")
    except TypeError:
        return RunContext.model_construct(deps=deps)  # type: ignore[attr-defined]
```

If `RunContext` still cannot be built, call an internal helper: keep public tools as specified, and have each tool call `_run_read_file(deps, path)` etc., and test those helpers. Prefer constructing `RunContext` first.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_tools.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'termagent.tools'`

- [ ] **Step 3: Write tools**

```python
# src/termagent/tools.py
from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import RunContext

from termagent.sandbox import SandboxError, resolve_in_workspace

SHELL_TIMEOUT = 30


@dataclass
class AgentDeps:
    workspace: Path
    on_tool: Callable[[str, dict[str, object]], None] | None = field(default=None)


def _notify(ctx: RunContext[AgentDeps], name: str, args: dict[str, object]) -> None:
    if ctx.deps.on_tool is not None:
        ctx.deps.on_tool(name, args)


def _error(exc: BaseException) -> str:
    return f"error: {exc}"


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
    _notify(ctx, "write_file", {"path": path})
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
    _notify(ctx, "run_shell", {"command": command})
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_tools.py tests/test_sandbox.py -v`

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/termagent/tools.py tests/test_tools.py
git commit -m "feat: add sandboxed file and shell tools"
```

---

### Task 3: Agent + session loop

**Files:**
- Create: `src/termagent/agent.py`
- Create: `tests/test_agent_loop.py`

**Interfaces:**
- Consumes: `AgentDeps`, `read_file`, `write_file`, `list_dir`, `run_shell` from `termagent.tools`
- Produces:
  - `INSTRUCTIONS: str` (coding-agent system prompt)
  - `def build_agent(model: str | Model) -> Agent[AgentDeps, str]`
  - `class CodingSession` with `__init__(self, agent: Agent[AgentDeps, str], deps: AgentDeps)`, `reset(self) -> None`, `async def run(self, prompt: str) -> str`, and `history` list
  - `CodingSession.run` calls `await self.agent.run(prompt, deps=self.deps, message_history=self.history)` then `self.history = result.all_messages()` and returns `result.output`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_loop.py
from pathlib import Path

from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from termagent.agent import CodingSession, build_agent
from termagent.tools import AgentDeps


def _scripted(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    if len(messages) == 1:
        return ModelResponse(parts=[ToolCallPart("list_dir", {"path": "."})])
    return ModelResponse(parts=[TextPart("I see hello.txt")])


async def test_agent_calls_list_dir_then_replies(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []

    def on_tool(name: str, args: dict[str, object]) -> None:
        calls.append((name, args))

    agent = build_agent(FunctionModel(_scripted))
    session = CodingSession(agent, AgentDeps(workspace=tmp_path, on_tool=on_tool))
    output = await session.run("what files are here?")
    assert output == "I see hello.txt"
    assert calls and calls[0][0] == "list_dir"


async def test_reset_clears_history(tmp_path: Path) -> None:
    agent = build_agent(FunctionModel(_scripted))
    session = CodingSession(agent, AgentDeps(workspace=tmp_path))
    await session.run("what files are here?")
    assert session.history
    session.reset()
    assert session.history == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent_loop.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'termagent.agent'`

- [ ] **Step 3: Write agent + session**

```python
# src/termagent/agent.py
from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model

from termagent.tools import AgentDeps, list_dir, read_file, run_shell, write_file

INSTRUCTIONS = """You are a coding agent working in a local workspace.
Use tools to inspect and edit files. Stay inside the workspace.
Prefer small, targeted edits. After finishing, summarize what you did."""


def build_agent(model: str | Model) -> Agent[AgentDeps, str]:
    return Agent(
        model,
        deps_type=AgentDeps,
        instructions=INSTRUCTIONS,
        tools=[read_file, write_file, list_dir, run_shell],
    )


class CodingSession:
    def __init__(self, agent: Agent[AgentDeps, str], deps: AgentDeps) -> None:
        self.agent = agent
        self.deps = deps
        self.history: list[ModelMessage] = []

    def reset(self) -> None:
        self.history = []

    async def run(self, prompt: str) -> str:
        result = await self.agent.run(
            prompt,
            deps=self.deps,
            message_history=self.history,
        )
        self.history = result.all_messages()
        return result.output
```

If `pydantic_ai.messages.ModelMessage` is the wrong import path, use `from pydantic_ai import ModelMessage` as in the test.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_agent_loop.py tests/test_tools.py -v`

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/termagent/agent.py tests/test_agent_loop.py
git commit -m "feat: add PydanticAI session loop with mockable model"
```

---

### Task 4: Config + CLI entry

**Files:**
- Create: `src/termagent/config.py`
- Create: `src/termagent/__main__.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing from agent/tools except types used when wiring in `__main__`
- Produces:
  - `class ConfigError(SystemExit)` (or raise `SystemExit` directly)
  - `@dataclass(frozen=True) class Config: api_key: str; model: str; workspace: Path`
  - `def load_config(workspace: Path | None = None) -> Config` — calls `load_dotenv()`, requires `OPENAI_API_KEY`, default model `gpt-4o-mini`, workspace = given path or `Path.cwd()`, both resolved
  - `def main() -> None` in `__main__.py` — argparse `--workspace`, `load_config`, print error and return if config fails, otherwise `TermagentApp(...).run()`. For this task, if `tui` is not written yet, `main()` should still parse args and load config; call TUI only if import works. Prefer: `__main__.py` imports TUI and Task 5 fills TUI. For Task 4, implement `main()` to load config then `from termagent.tui import run_app; run_app(config)` — Task 5 implements `run_app`. Until then, tests only cover `load_config`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_config.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'termagent.config'`

- [ ] **Step 3: Write config and __main__**

```python
# src/termagent/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os


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
```

```python
# src/termagent/__main__.py
from __future__ import annotations

import argparse
from pathlib import Path

from termagent.config import ConfigError, load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="termagent")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (default: current directory)",
    )
    args = parser.parse_args()
    try:
        config = load_config(args.workspace)
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc
    from termagent.tui import run_app

    run_app(config)


if __name__ == "__main__":
    main()
```

Do not run `python -m termagent` until Task 5 adds `run_app`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config.py tests/test_sandbox.py -v`

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/termagent/config.py src/termagent/__main__.py tests/test_config.py
git commit -m "feat: load API key, model, and workspace from env"
```

---

### Task 5: Textual TUI

**Files:**
- Create: `src/termagent/tui.py`

**Interfaces:**
- Consumes: `Config`; `build_agent`, `CodingSession`; `AgentDeps`
- Produces: `def run_app(config: Config) -> None` which builds `OpenAIChatModel(config.model, provider=OpenAIProvider(api_key=config.api_key))`, `CodingSession`, and runs `TermagentApp`

TUI behavior:
- Header title `termagent`; subtitle `{workspace}  {model}`
- `RichLog` transcript
- `Input` at bottom; Enter submits
- `/quit` exits, `/reset` clears session history and notes it in the log, `/help` prints command list
- On a normal prompt: append `you: ...`, disable input, run session in a `@work(exclusive=True)` worker, `on_tool` appends `→ name args`, then append `agent: ...` or `error: ...`, re-enable input
- Ignore Enter while `input.disabled` is True (exclusive worker + disabled input)

- [ ] **Step 1: Write a small import/smoke test**

There is no full TUI snapshot test. Add this to `tests/test_agent_loop.py` (or `tests/test_tui.py`):

```python
# tests/test_tui.py
from termagent.tui import TermagentApp, run_app


def test_app_class_exists() -> None:
    assert TermagentApp is not None
    assert callable(run_app)
```

This will fail until `tui.py` exists.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tui.py -v`

Expected: FAIL import error

- [ ] **Step 3: Implement TUI**

```python
# src/termagent/tui.py
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Input, RichLog
from textual.worker import Worker, WorkerState
from textual.work import work
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from termagent.agent import CodingSession, build_agent
from termagent.config import Config
from termagent.tools import AgentDeps

HELP = """/help — this message
/reset — clear session history
/quit — exit
Anything else is sent to the coding agent."""


class TermagentApp(App[None]):
    CSS = """
    RichLog {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }
    Input {
        dock: bottom;
    }
    """
    BINDINGS = [Binding("ctrl+c", "quit", "Quit", show=False)]

    def __init__(self, session: CodingSession, config: Config) -> None:
        super().__init__()
        self.session = session
        self.config = config
        self.title = "termagent"
        self.sub_title = f"{config.workspace}  {config.model}"

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", highlight=True, markup=True)
        yield Input(placeholder="Task, or /help", id="prompt")

    def on_mount(self) -> None:
        self.query_one("#log", RichLog).write("Ready. Type a task or /help.")
        self.query_one("#prompt", Input).focus()

    def _log(self, message: str) -> None:
        self.query_one("#log", RichLog).write(message)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value.strip()
        event.input.value = ""
        if not prompt or event.input.disabled:
            return
        if prompt == "/quit":
            self.exit()
            return
        if prompt == "/reset":
            self.session.reset()
            self._log("history cleared")
            return
        if prompt == "/help":
            self._log(HELP)
            return
        event.input.disabled = True
        self._log(f"you: {prompt}")
        self.run_task(prompt)

    def _on_tool(self, name: str, args: dict[str, object]) -> None:
        self.call_from_thread(self._log, f"→ {name} {args}")

    @work(exclusive=True)
    async def run_task(self, prompt: str) -> str:
        self.session.deps.on_tool = self._on_tool
        return await self.session.run(prompt)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "run_task":
            return
        prompt = self.query_one("#prompt", Input)
        if event.state == WorkerState.SUCCESS:
            self._log(f"agent: {event.worker.result}")
            prompt.disabled = False
            prompt.focus()
        elif event.state == WorkerState.ERROR:
            self._log(f"error: {event.worker.error}")
            prompt.disabled = False
            prompt.focus()


def run_app(config: Config) -> None:
    model = OpenAIChatModel(
        config.model,
        provider=OpenAIProvider(api_key=config.api_key),
    )
    deps = AgentDeps(workspace=config.workspace)
    session = CodingSession(build_agent(model), deps)
    TermagentApp(session, config).run()
```

If `@work` methods do not set `worker.name` to `run_task`, match on `event.worker.get_name()` or skip the name check and treat any finished exclusive worker as the agent run. If `call_from_thread` errors because the worker is async on the app thread, call `self._log` directly from `_on_tool`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -v`

Expected: all passed, including `tests/test_tui.py`

- [ ] **Step 5: Commit**

```bash
git add src/termagent/tui.py tests/test_tui.py
git commit -m "feat: add Textual TUI for the coding agent"
```

---

### Task 6: README + env example

**Files:**
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Consumes: CLI `python -m termagent [--workspace PATH]`
- Produces: docs only

- [ ] **Step 1: Write files**

```
# .env.example
OPENAI_API_KEY=
AGENT_MODEL=gpt-4o-mini
```

```markdown
# termagent

A small terminal coding agent. Type a task; watch it read/write files and run shell commands inside a workspace.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# put your OpenAI-compatible key in .env
```

## Run

```bash
python -m termagent
python -m termagent --workspace /path/to/repo
```

`OPENAI_API_KEY` is required. `AGENT_MODEL` defaults to `gpt-4o-mini`. Any OpenAI-compatible provider works if you also set `OPENAI_BASE_URL` (see pydantic-ai OpenAI provider).

Commands inside the TUI: `/help`, `/reset`, `/quit`.

## Tests

```bash
pytest
```
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/pytest -v`

Expected: all passed

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: add setup and run instructions"
```

---

## Self-review

1. Spec coverage: sandbox, four tools, agent loop, config/env, TUI header/transcript/input/slash commands/one-run-at-a-time, errors as strings, pytest without live API, README — each has a task.
2. No TBD/placeholder steps.
3. Names: `AgentDeps`, `CodingSession.run`, `build_agent`, `load_config`, `run_app`, `SHELL_TIMEOUT`, `ConfigError` are consistent across tasks.
4. `AgentDeps` lives in `tools.py` (not `agent.py`) so tools do not import `agent.py`.
