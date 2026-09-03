from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Input, RichLog
from textual.worker import Worker, WorkerState
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
        self.transcript: list[str] = []
        self._live_agent = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", highlight=True, markup=True)
        yield Input(placeholder="Task, or /help", id="prompt")

    def on_mount(self) -> None:
        self._log("Ready. Type a task or /help.")
        self.query_one("#prompt", Input).focus()

    def _render_transcript(self) -> None:
        log = self.query_one("#log", RichLog)
        log.clear()
        for message in self.transcript:
            log.write(message)

    def _log(self, message: str) -> None:
        self._live_agent = False
        self.transcript.append(message)
        self.query_one("#log", RichLog).write(message)

    def _set_agent_line(self, line: str) -> None:
        if self._live_agent and self.transcript and self.transcript[-1].startswith("agent: "):
            self.transcript[-1] = line
            self._render_transcript()
        else:
            self.transcript.append(line)
            self._live_agent = True
            self.query_one("#log", RichLog).write(line)

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
        line = f"→ {name} {args}"
        try:
            self.call_from_thread(self._log, line)
        except RuntimeError:
            self._log(line)

    def _on_text(self, text: str) -> None:
        line = f"agent: {text}"
        try:
            self.call_from_thread(self._set_agent_line, line)
        except RuntimeError:
            self._set_agent_line(line)

    @work(exclusive=True, name="run_task", exit_on_error=False)
    async def run_task(self, prompt: str) -> str:
        self.session.deps.on_tool = self._on_tool
        self._live_agent = False
        return await self.session.run_stream(prompt, on_text=self._on_text)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if getattr(event.worker, "name", "") != "run_task":
            return
        prompt = self.query_one("#prompt", Input)
        if event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result is not None and not (
                self.transcript and self.transcript[-1].startswith("agent: ")
            ):
                self._log(f"agent: {result}")
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
