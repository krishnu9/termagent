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
python -m termagent --workspace ~/Developer/my-app
```

With no flag, the workspace is the **current directory**. If the `--workspace` path does not exist, termagent creates it. That is enough to start a new project.

`OPENAI_API_KEY` is required. `AGENT_MODEL` defaults to `gpt-4o-mini`. Any OpenAI-compatible provider works if you also set `OPENAI_BASE_URL` (see pydantic-ai OpenAI provider).

Commands inside the TUI: `/help`, `/reset`, `/quit`.

## Tests

```bash
pytest
```
