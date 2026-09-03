from __future__ import annotations

from collections.abc import Callable

from pydantic_ai import Agent, ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from termagent.config import Config
from termagent.tools import AgentDeps, list_dir, read_file, run_shell, search_text, write_file

INSTRUCTIONS = """You are a coding agent working in a local workspace.
Use tools to inspect and edit files. Stay inside the workspace.
Prefer small, targeted edits. After finishing, summarize what you did."""


def create_chat_model(config: Config) -> OpenAIChatModel:
    provider = OpenAIProvider(api_key=config.api_key, base_url=config.base_url)
    return OpenAIChatModel(config.model, provider=provider)


def build_agent(model: str | Model) -> Agent[AgentDeps, str]:
    return Agent(
        model,
        deps_type=AgentDeps,
        instructions=INSTRUCTIONS,
        tools=[read_file, write_file, list_dir, search_text, run_shell],
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

    async def run_stream(
        self,
        prompt: str,
        on_text: Callable[[str], None] | None = None,
    ) -> str:
        async with self.agent.run_stream(
            prompt,
            deps=self.deps,
            message_history=self.history,
        ) as result:
            async for text in result.stream_text(delta=False, debounce_by=None):
                if on_text is not None:
                    on_text(text)
            output = await result.get_output()
            self.history = result.all_messages()
            return output
