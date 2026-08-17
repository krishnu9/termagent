from __future__ import annotations

from pydantic_ai import Agent, ModelMessage
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
