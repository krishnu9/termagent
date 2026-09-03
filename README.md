# termagent

A small terminal coding agent. Type a task; watch it read/write files and run shell commands inside a workspace. Assistant replies **stream into the TUI** as tokens arrive (`agent:` line updates live). Tool traces (`→ name args`) still appear as they run.

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
