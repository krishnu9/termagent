from __future__ import annotations

import threading

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Header, Input, Label, RichLog, Static
from textual.worker import Worker, WorkerState

from termagent.agent import CodingSession, build_agent, create_chat_model
from termagent.config import Config
from termagent.tools import AgentDeps

HELP = """/help — this message
/reset — clear session history
/quit — exit
Anything else is sent to the coding agent.

write_file and run_shell ask for confirmation (y/n) unless you started with --yes."""


class PermissionScreen(ModalScreen[bool]):
    """Blocking y/n confirmation for gated tools."""

    CSS = """
    PermissionScreen {
        align: center middle;
    }
    #confirm {
        width: 80%;
        max-width: 80;
        height: auto;
        border: heavy $warning;
        background: $surface;
        padding: 1 2;
    }
    """
    BINDINGS = [
        Binding("y", "accept", "Yes", show=True),
        Binding("n", "reject", "No", show=True),
        Binding("escape", "reject", "No", show=False),
    ]

    def __init__(self, tool: str, args: dict[str, object]) -> None:
        super().__init__()
        self._tool = tool
        self._args = args

    def compose(self) -> ComposeResult:
        preview = ", ".join(f"{k}={v!r}" for k, v in self._args.items())
        if len(preview) > 400:
            preview = preview[:400] + "…"
        with Vertical(id="confirm"):
            yield Label(f"Allow {self._tool}?")
            yield Static(preview)
            yield Static("Press [b]y[/b] to allow, [b]n[/b] to deny.", markup=True)

    def action_accept(self) -> None:
        self.dismiss(True)

    def action_reject(self) -> None:
        self.dismiss(False)


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

    def request_approval(self, name: str, args: dict[str, object]) -> bool:
        """Block the tool thread until the user answers y/n on the app thread."""
        if self.config.auto_approve:
            return True
        done = threading.Event()
        box: dict[str, bool] = {"ok": False}

        def show() -> None:
            def dismissed(result: bool | None) -> None:
                box["ok"] = bool(result)
                done.set()

            self._log(f"? {name} — y to allow, n to deny")
            self.push_screen(PermissionScreen(name, args), dismissed)

        self.call_from_thread(show)
        done.wait()
        return box["ok"]

    def _on_text(self, text: str) -> None:
        line = f"agent: {text}"
        try:
            self.call_from_thread(self._set_agent_line, line)
        except RuntimeError:
            self._set_agent_line(line)

    @work(exclusive=True, name="run_task", exit_on_error=False)
    async def run_task(self, prompt: str) -> str:
        self.session.deps.on_tool = self._on_tool
        self.session.deps.approve = self.request_approval
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
    deps = AgentDeps(
        workspace=config.workspace, auto_approve=config.auto_approve
    )
    session = CodingSession(build_agent(create_chat_model(config)), deps)
    TermagentApp(session, config).run()
