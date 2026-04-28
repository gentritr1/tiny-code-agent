from pathlib import Path
from typing import Any

from tiny_code_agent.agent import CodingAgent
from tiny_code_agent.llm import AssistantTurn, LLMProviderError, ToolCall, ToolCallResult
from tiny_code_agent.tools import build_tool_registry


class FakeClient:
    provider_name = "fake"

    def __init__(self) -> None:
        self.messages: list[list[dict[str, Any]]] = []
        self.previous_response_ids: list[str | None] = []

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Any],
        instructions: str,
        previous_response_id: str | None = None,
    ) -> AssistantTurn:
        self.messages.append(list(messages))
        self.previous_response_ids.append(previous_response_id)
        if len(self.messages) == 1:
            return AssistantTurn(
                response_id="resp_1",
                messages=[{"role": "assistant", "content": "Calling edit_file."}],
                text="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="edit_file",
                        arguments={"path": "hello.py", "old_str": "", "new_str": "print('hi')\n"},
                    )
                ],
            )
        return AssistantTurn(
            response_id="resp_2",
            messages=[{"role": "assistant", "content": "Created hello.py."}],
            text="Created hello.py.",
            tool_calls=[],
        )

    def tool_result_message(self, result: ToolCallResult) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": result.call_id,
            "name": result.name,
            "content": result.output,
        }


def test_agent_executes_tool_and_returns_final_answer(tmp_path: Path) -> None:
    client = FakeClient()
    printed: list[str] = []
    agent = CodingAgent(
        client=client,
        model="test-model",
        registry=build_tool_registry(tmp_path),
        printer=printed.append,
    )

    answer = agent.ask("create hello.py")

    assert answer == "Created hello.py."
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "print('hi')\n"
    assert client.messages[-1][-1]["role"] == "tool"
    assert client.messages[-1][-1]["content"]["action"] == "created_file"
    assert client.messages[0] == [{"role": "user", "content": "create hello.py"}]
    assert client.previous_response_ids == [None, "resp_1"]
    assert printed[0].startswith("tool: edit_file")
    assert printed[1].startswith("tool_result: edit_file")


class FailingClient:
    provider_name = "fake"

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Any],
        instructions: str,
        previous_response_id: str | None = None,
    ) -> AssistantTurn:
        raise LLMProviderError("quota exceeded")

    def tool_result_message(self, result: ToolCallResult) -> dict[str, Any]:
        raise AssertionError("tool_result_message should not be called")


def test_agent_rolls_back_failed_turn_from_history(tmp_path: Path) -> None:
    agent = CodingAgent(client=FailingClient(), model="test-model", registry=build_tool_registry(tmp_path))

    try:
        agent.ask("create hello.py")
    except LLMProviderError as exc:
        assert exc.message == "quota exceeded"
    else:
        raise AssertionError("expected LLMProviderError")

    assert agent.messages == []


class LoopingClient:
    provider_name = "fake"

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Any],
        instructions: str,
        previous_response_id: str | None = None,
    ) -> AssistantTurn:
        return AssistantTurn(
            response_id="resp_loop",
            messages=[{"role": "assistant", "content": "Still working."}],
            text="",
            tool_calls=[ToolCall(id="loop", name="missing_tool", arguments={})],
        )

    def tool_result_message(self, result: ToolCallResult) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": result.call_id,
            "name": result.name,
            "content": result.output,
        }


def test_agent_stops_when_tool_loop_limit_is_hit(tmp_path: Path) -> None:
    agent = CodingAgent(client=LoopingClient(), model="test-model", registry=build_tool_registry(tmp_path))

    answer = agent.ask("keep looping")

    assert answer == "Stopped because the tool loop exceeded the safety limit."
