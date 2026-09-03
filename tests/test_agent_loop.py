from pathlib import Path

from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from termagent.agent import CodingSession, build_agent
from termagent.tools import AgentDeps


def _scripted(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    if len(messages) == 1:
        return ModelResponse(parts=[ToolCallPart("list_dir", {"path": "."})])
    return ModelResponse(parts=[TextPart("I see hello.txt")])


async def _stream_scripted(messages: list[ModelMessage], _info: AgentInfo):
    if len(messages) == 1:
        yield {
            0: DeltaToolCall(
                name="list_dir",
                json_args='{"path": "."}',
                tool_call_id="list-1",
            )
        }
        return
    yield "I see "
    yield "hello.txt"


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


async def test_run_stream_yields_text_and_keeps_tools(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    calls: list[tuple[str, dict[str, object]]] = []
    chunks: list[str] = []

    def on_tool(name: str, args: dict[str, object]) -> None:
        calls.append((name, args))

    def on_text(text: str) -> None:
        chunks.append(text)

    agent = build_agent(FunctionModel(_scripted, stream_function=_stream_scripted))
    session = CodingSession(agent, AgentDeps(workspace=tmp_path, on_tool=on_tool))
    output = await session.run_stream("what files are here?", on_text=on_text)
    assert output == "I see hello.txt"
    assert chunks
    assert chunks[-1] == "I see hello.txt"
    assert any(c == "I see " or c.startswith("I see") for c in chunks)
    assert calls and calls[0][0] == "list_dir"
    assert session.history
