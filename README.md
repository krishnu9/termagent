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

## Tools

| Tool | Behavior |
|------|----------|
| `read_file` | Read a UTF-8 text file, capped at 100,000 characters (truncated files include a notice) |
| `write_file` | Create or overwrite a UTF-8 text file |
| `list_dir` | List directory entries, skipping junk dirs (`.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `build`, `.pytest_cache`, `*.egg-info`) |
| `search_text` | Regex/string search (`rg` if available, else a Python walk); same ignore rules; capped matches and line snippets |
| `run_shell` | `subprocess` with `cwd=workspace`, 30s timeout |

`list_dir` and `search_text` skip well-known junk so a real repo does not dump huge trees into the model; `read_file` truncates oversized files so you can search instead of assuming the full contents were loaded.

## Tests

```bash
pytest
```
