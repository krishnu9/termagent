from pathlib import Path

from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from termagent.agent import CodingSession, build_agent
from termagent.tools import AgentDeps


def _scripted(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    if len(messages) == 1:
        return ModelResponse(parts=[ToolCallPart("list_dir", {"path": "."})])
    return ModelResponse(parts=[TextPart("I see hello.txt")])


async def test_agent_calls_list_dir_then_replies(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []

    def on_tool(name: str, args: dict[str, object]) -> None:
        calls.append((name, args))

    agent = build_agent(FunctionModel(_scripted))
    session = CodingSession(agent, AgentDeps(workspace=tmp_path, on_tool=on_tool))
    output = await session.run("what files are here?")
    assert output == "I see hello.txt"
    assert calls and calls[0][0] == "list_dir"


async def test_reset_clears_history(tmp_path: Path) -> None:
    agent = build_agent(FunctionModel(_scripted))
    session = CodingSession(agent, AgentDeps(workspace=tmp_path))
    await session.run("what files are here?")
    assert session.history
    session.reset()
    assert session.history == []
