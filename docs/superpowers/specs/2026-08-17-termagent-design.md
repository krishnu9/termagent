# termagent — terminal coding agent (v1)

Date: 2026-08-17  
Status: approved for implementation planning

## Goal

A small Python CLI that teaches the coding-agent loop: user task → model → tool calls → execute → feed results back → repeat until the model stops calling tools.

v1 is a personal learning project you can run on a local workspace. It is not a product, not a Cursor/Claude Code clone, and not a multi-agent system.

Success looks like: you type “add a --verbose flag and run tests,” watch `read_file` / `write_file` / `run_shell` fire in the TUI, and get a final reply without the process crashing.

## Non-goals (v1)

- Streaming tokens
- Git awareness
- Web search, MCP, plugins
- Persistent chat history across restarts
- Confirm-before-write / confirm-before-shell prompts
- Multi-agent / subagents
- Path-escape attacks beyond a workspace-root check

## Architecture

```
you (Textual TUI) → PydanticAI agent → OpenAI-compatible model
                         ↓
                 tools: read / write / list / shell
                         ↓
                 sandbox: paths + cwd stay inside workspace
```

The TUI only renders and drives one `agent.run(...)` at a time. Tools never talk to the TUI. The sandbox is the only safety layer.

## Components

### TUI (`src/termagent/tui.py`)

Textual app, one screen:

- Header: `termagent`, workspace path, model name
- Transcript: user messages, tool calls (`→ name args`), agent replies, errors
- Input: task text; Enter sends. `/quit`, `/reset`, `/help` work from this box

While a run is in progress, input is ignored so two loops cannot overlap.

### Agent (`src/termagent/agent.py`)

PydanticAI `Agent` with a short system prompt: you are a coding agent; use tools; stay inside the workspace; prefer small edits.

Holds in-memory message history for the session. `/reset` clears it. Model name comes from config.

### Tools (`src/termagent/tools.py`)

| Tool | Behavior |
|------|----------|
| `read_file(path)` | Read a UTF-8 text file; return contents or an error string |
| `write_file(path, content)` | Create or overwrite a UTF-8 text file |
| `list_dir(path)` | List directory entries (names + file/dir) |
| `run_shell(command)` | `subprocess` with `cwd=workspace`, timeout 30s; return stdout, stderr, exit code |

Tools catch their own failures and return text. They do not raise into the TUI.

### Sandbox (`src/termagent/sandbox.py`)

Resolves `path` against the workspace root (`Path.resolve()`). Relative paths and absolute paths *inside* the workspace are allowed. Anything whose resolved path is not under the workspace is rejected.

`run_shell` is not a filesystem jail: the subprocess starts with `cwd=workspace` and a 30s timeout, but the command itself can still touch files outside (e.g. `cat /etc/passwd`). v1 does not wrap the shell in a container or OS sandbox.

### Config (`src/termagent/config.py`)

Loaded from environment (optional `.env`):

- `OPENAI_API_KEY` — required at startup
- `AGENT_MODEL` — default `gpt-4o-mini`
- Workspace — `--workspace` CLI flag, default `cwd`

OpenAI-compatible on purpose: Groq, OpenRouter, or a local proxy can be swapped later by changing base URL/model without rewriting tools.

### Entry (`src/termagent/__main__.py`)

`python -m termagent [--workspace PATH]`

## Layout

```
termagent/
  pyproject.toml
  .env.example
  README.md
  docs/superpowers/specs/2026-08-17-termagent-design.md
  src/termagent/
    __init__.py
    __main__.py
    tui.py
    agent.py
    tools.py
    sandbox.py
    config.py
  tests/
    test_sandbox.py
    test_tools.py
    test_agent_loop.py
```

Install: `pip install -e ".[dev]"` with runtime deps `pydantic-ai`, `textual`, `python-dotenv` and dev extra `pytest`.

## Data flow

1. User submits a task in the TUI.
2. TUI appends a user message, disables input, calls `agent.run(history)`.
3. PydanticAI sends messages + tool schemas to the model.
4. If the model returns tool calls: sandbox each path (or run shell), print `→ tool args` in the transcript, append tool results to history, call the model again.
5. Repeat until the model returns text with no tool calls.
6. TUI appends the final reply and re-enables input.

History is session-only RAM. Disk writes happen only through `write_file`.

## Error handling

| Failure | Behavior |
|---------|----------|
| Missing API key or invalid model at startup | Print a clear message and exit before the TUI starts |
| Path escapes workspace | Tool result is an error string; TUI still shows the call |
| File not found / permission / decode error | Error string back to the model |
| Shell timeout (30s) or non-zero exit | stdout, stderr, and exit code as the tool result |
| Model/API error mid-run | Transcript shows the error; input re-enabled; history kept |

## Testing

No live API in tests. TUI is not required for CI.

- Sandbox: `foo.txt` allowed; `../etc/passwd` and absolute paths outside the workspace rejected
- Tools: `write_file` then `read_file` round-trip in a temp workspace; `list_dir` sees the file; `run_shell` cwd is the workspace; timeout is enforced
- Agent loop: fake/mock model first requests `list_dir`, then returns a final sentence; assert the tool ran and the caller received the final text

`pytest` via `pyproject.toml`.

## Implementation order (for the plan)

1. Package skeleton + config
2. Sandbox + tests
3. Tools + tests
4. Agent with a mockable model + loop test
5. Textual TUI wired to the agent
6. README: key, model, `python -m termagent`

## Decisions already made

- Language: Python
- Framework: PydanticAI (not a from-scratch loop, not LangGraph)
- UI: Textual TUI (not `input()`, not streaming)
- v1 tools: read, write, list, shell
- Model: OpenAI-compatible; simplest key-based setup
- No transcript persistence, no permission prompts
