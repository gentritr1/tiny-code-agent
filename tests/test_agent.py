from pathlib import Path
from typing import Any

from tiny_code_agent.agent import CodingAgent
from tiny_code_agent.llm import AssistantTurn, ToolCall, ToolCallResult
from tiny_code_agent.tools import build_tool_registry


class FakeClient:
    provider_name = "fake"

    def __init__(self) -> None:
        self.messages: list[list[dict[str, Any]]] = []

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Any],
        instructions: str,
    ) -> AssistantTurn:
        self.messages.append(list(messages))
        if len(self.messages) == 1:
            return AssistantTurn(
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
    agent = CodingAgent(client=client, model="test-model", registry=build_tool_registry(tmp_path))

    answer = agent.ask("create hello.py")

    assert answer == "Created hello.py."
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "print('hi')\n"
    assert client.messages[-1][-1]["role"] == "tool"
    assert client.messages[-1][-1]["content"]["action"] == "created_file"
