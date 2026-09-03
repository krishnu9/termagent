# termagent

A small terminal coding agent. Type a task; a language model calls tools; Python executes those tools on disk; results go back to the model until it answers in plain text.

This is a learning project for the **tool loop** used by agents like Cursor and Claude Code. It is not a product clone.

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

With no flag, the workspace is the **current directory**. If you start the app from this repo, it will edit this repo. Point `--workspace` at another folder (create it first if needed):

```bash
mkdir -p ~/Developer/my-app
python -m termagent --workspace ~/Developer/my-app
```

The TUI header shows workspace path and model name. Check that before you type a task.

Keys still load from this project's `.env`. Only file and shell tools are scoped to `--workspace`.

TUI commands: `/help`, `/reset`, `/quit`.

## Config

| Variable | Role |
|----------|------|
| `OPENAI_API_KEY` | Required (unless `OPENROUTER_API_KEY` is set) |
| `OPENROUTER_API_KEY` | Used if `OPENAI_API_KEY` is empty |
| `AGENT_MODEL` | Defaults to `gpt-4o-mini` |
| `OPENAI_BASE_URL` | Optional override for any OpenAI-compatible host |

OpenRouter keys (`sk-or-v1-...`) are detected automatically and sent to `https://openrouter.ai/api/v1`. An OpenRouter key sent to OpenAI's default host returns 401 from `platform.openai.com`.

## Tests

```bash
pytest
```

No live API in CI. Tests fake the model (`FunctionModel`) and isolate `.env` so local keys do not leak into assertions.

---

## What it is (interview pitch)

termagent is a terminal coding agent: you type a task, a language model decides whether to call tools, Python executes those tools on disk, results go back to the model, and that repeats until the model answers in plain text. The interesting part is not the TUI — it is the **tool loop**.

An LLM cannot touch your filesystem. It only returns structured output: “call `read_file` with `path=src/cli.py`.” This process runs that function and sends the result back as another message. The model then either calls more tools or stops with a final reply.

ChatGPT is one request → one answer. An agent is a **state machine** whose transitions are tool calls.

## Architecture

```
CLI / config
    → Textual TUI          # renderer only; one run at a time
        → CodingSession    # history + agent.run()
            → PydanticAI   # model I/O + tool dispatch
                → tools    # read / write / list / shell
                    → sandbox   # path must stay under workspace
                → OpenAI-compatible HTTP  # OpenAI, OpenRouter, …
```

| File | Job |
|------|-----|
| `src/termagent/__main__.py` | Parse `--workspace`, load config, start TUI |
| `src/termagent/config.py` | API key, model, base URL, workspace path |
| `src/termagent/tui.py` | Transcript + input; does **not** implement tools |
| `src/termagent/agent.py` | System prompt, tool registration, session history |
| `src/termagent/tools.py` | Side effects (disk/shell); always return `str` |
| `src/termagent/sandbox.py` | Path confinement |

UI, orchestration, and side effects are separate. Tools can be tested without a TUI. The loop can be tested with a fake model and no API key.

## The agent loop

`CodingSession.run` is one user turn. Inside it, PydanticAI may round-trip the model many times:

1. Send system instructions, history, the user message, and JSON schemas derived from the four tool functions (docstrings become tool descriptions).
2. If the model returns tool calls: execute them, append results to history, call the model again.
3. Stop when the model returns text with no tool calls.

History is **in-memory only**. `/reset` drops it. Nothing is persisted across restarts.

## A single turn

1. `python -m termagent --workspace ~/Developer/my-app` loads config and builds `AgentDeps(workspace=…)` plus a `CodingSession`.
2. You type a task. Input is **disabled** so two loops cannot overlap. A Textual worker (`@work(exclusive=True)`) calls `session.run`.
3. Each tool fires `on_tool` so the TUI can print `→ read_file {path: ...}`, then resolves the path through the sandbox, then returns **text** (including `error: …`).
4. Tool results go back to the model until it answers.
5. The TUI prints `agent: …` and re-enables input. API failures show as `error:`; history is kept.

## Tools

| Tool | Behavior |
|------|----------|
| `read_file` | Read a UTF-8 text file |
| `write_file` | Create or overwrite a UTF-8 text file |
| `list_dir` | List directory entries |
| `run_shell` | `subprocess` with `cwd=workspace`, 30s timeout; returns stdout, stderr, exit code |

Tools take `RunContext[AgentDeps]` so they see the workspace without globals. They **never raise into the TUI**. A missing file or a path escape becomes a string the model can read and recover from. Errors are part of the agent's observation stream, not control-flow exceptions.

`run_shell` treats a non-zero exit as a successful tool result — failing tests are information, not a crash.

## Sandbox vs jail

File tools resolve paths with `Path.resolve()` and reject anything whose resolved path is not under the workspace (`../etc/passwd`, absolute paths outside). Relative paths and absolute paths *inside* the workspace are allowed.

`run_shell` is **not** a filesystem jail: the subprocess starts with `cwd=workspace` and a timeout, but the command can still touch files outside (for example `cat /etc/passwd`). v1 does not use a container or OS sandbox.

## Design decisions

- **PydanticAI, not LangGraph.** The product is the tool loop, not a graph framework. Tools are typed functions; `deps_type` injects workspace.
- **OpenAI-compatible provider.** Same client for OpenAI, OpenRouter, Groq. Model is swappable; tools are not.
- **TUI is a renderer.** Live tool traces use `AgentDeps.on_tool`, not parsing of the model API.
- **Tests use `FunctionModel`.** A fake model first emits `list_dir`, then a final sentence. CI never hits a live API (`ALLOW_MODEL_REQUESTS = False`).
- **YAGNI for v1.** No streaming, git, MCP, persistence, or permission prompts. Those sit on top of the same loop.

## Known limitations

- No token streaming
- No git awareness
- No web search, MCP, or plugins
- No transcript persistence across restarts
- No confirm-before-write / confirm-before-shell
- No multi-agent / subagents
- Path checks only; shell is not jailed
- File tools do not cap size; a huge file can blow the context window
- One agent run at a time (input disabled while working)

## Possible improvements

Highest leverage first, all on the same loop:

1. **Create `--workspace` if missing** so a new project is one command.
2. **Permission prompts** for `write_file` / `run_shell` (and a `--yes` escape).
3. **Streaming** tokens into the transcript (`run_stream`) — UX, not a new architecture.
4. **Context hygiene:** skip `node_modules` / `.git`, cap `read_file` size, maybe ripgrep instead of dumping whole files.
5. **Git tools** (`git_status`, `git_diff`) so the model sees repo state.
6. **Session persistence** (save/load PydanticAI message history).
7. **Shell confinement** (reject `cd /`, or run in a subprocess with tighter limits). Do not pretend the current sandbox is a jail.
8. **Interrupt / cancel** the in-flight worker (Escape).
9. **MCP or extra tools** (web search, GitHub) after the core loop is solid.
10. **Subagents** last — they add coordination, not understanding of the loop.
