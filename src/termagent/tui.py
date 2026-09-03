from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Input, RichLog
from textual.worker import Worker, WorkerState

from termagent.agent import CodingSession, build_agent, create_chat_model
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
        line = f"→ {name} {args}"
        try:
            self.call_from_thread(self._log, line)
        except RuntimeError:
            self._log(line)

    @work(exclusive=True, name="run_task")
    async def run_task(self, prompt: str) -> str:
        self.session.deps.on_tool = self._on_tool
        return await self.session.run(prompt)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if getattr(event.worker, "name", "") != "run_task":
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
    deps = AgentDeps(workspace=config.workspace)
    session = CodingSession(build_agent(create_chat_model(config)), deps)
    TermagentApp(session, config).run()
