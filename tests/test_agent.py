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
        self.instructions: list[str] = []

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
        self.instructions.append(instructions)
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


class RejectedEditClient:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Any],
        instructions: str,
        previous_response_id: str | None = None,
    ) -> AssistantTurn:
        self.calls += 1
        return AssistantTurn(
            response_id="resp_rejected",
            messages=[{"role": "assistant", "content": "Trying write."}],
            text="",
            tool_calls=[
                ToolCall(
                    id="call_rejected",
                    name="append_file",
                    arguments={"path": "hello.py", "text": "extra\n"},
                )
            ],
        )

    def tool_result_message(self, result: ToolCallResult) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": result.call_id,
            "name": result.name,
            "content": result.output,
        }


class FailedWriteClient:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Any],
        instructions: str,
        previous_response_id: str | None = None,
    ) -> AssistantTurn:
        self.calls += 1
        return AssistantTurn(
            response_id="resp_failed_write",
            messages=[{"role": "assistant", "content": "Trying insert."}],
            text="",
            tool_calls=[
                ToolCall(
                    id="call_failed_write",
                    name="insert_before",
                    arguments={"path": "hello.py", "anchor": "missing", "text": "# note\n"},
                )
            ],
        )

    def tool_result_message(self, result: ToolCallResult) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": result.call_id,
            "name": result.name,
            "content": result.output,
        }


class SuccessfulWriteThenRetryClient:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[Any],
        instructions: str,
        previous_response_id: str | None = None,
    ) -> AssistantTurn:
        self.calls += 1
        if self.calls == 1:
            return AssistantTurn(
                response_id="resp_write",
                messages=[{"role": "assistant", "content": "Writing."}],
                text="",
                tool_calls=[
                    ToolCall(
                        id="call_write",
                        name="edit_file",
                        arguments={
                            "path": "hello.py",
                            "old_str": "hello",
                            "new_str": "hello from tiny agent",
                        },
                    )
                ],
            )
        return AssistantTurn(
            response_id="resp_unwanted",
            messages=[{"role": "assistant", "content": "Trying extra write."}],
            text="",
            tool_calls=[
                ToolCall(
                    id="call_extra",
                    name="append_file",
                    arguments={"path": "hello.py", "text": "extra\n"},
                )
            ],
        )

    def tool_result_message(self, result: ToolCallResult) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": result.call_id,
            "name": result.name,
            "content": result.output,
        }


def test_agent_stops_turn_when_edit_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("hello\n", encoding="utf-8")
    client = RejectedEditClient()
    printed: list[str] = []
    agent = CodingAgent(
        client=client,
        model="test-model",
        registry=build_tool_registry(tmp_path, confirm_edit=lambda path, action: False),
        printer=printed.append,
    )

    answer = agent.ask("append text")

    assert answer == "Edit rejected. No changes were made. Send a new request to try again."
    assert client.calls == 1
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "hello\n"
    assert printed[-1].startswith("tool_result: append_file")


def test_agent_stops_turn_when_write_tool_fails(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("hello\n", encoding="utf-8")
    client = FailedWriteClient()
    agent = CodingAgent(
        client=client,
        model="test-model",
        registry=build_tool_registry(tmp_path),
    )

    answer = agent.ask("insert text")

    assert answer == "Write failed with anchor_not_found. No changes were made."
    assert client.calls == 1
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "hello\n"


def test_agent_stops_turn_after_successful_write(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("hello\n", encoding="utf-8")
    client = SuccessfulWriteThenRetryClient()
    agent = CodingAgent(
        client=client,
        model="test-model",
        registry=build_tool_registry(tmp_path),
    )

    answer = agent.ask("update hello")

    assert answer == "Applied edited to hello.py. No further changes were made."
    assert client.calls == 1
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "hello from tiny agent\n"


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

    assert answer == "Applied created_file to hello.py. No further changes were made."
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "print('hi')\n"
    assert agent.messages[-1]["role"] == "tool"
    assert agent.messages[-1]["content"]["action"] == "created_file"
    assert client.messages[0] == [{"role": "user", "content": "create hello.py"}]
    assert "preview_edit_file" in client.instructions[0]
    assert "preview_append_file" in client.instructions[0]
    assert "append_file" in client.instructions[0]
    assert "insert_after" in client.instructions[0]
    assert "insert_before" in client.instructions[0]
    assert "list_tree" in client.instructions[0]
    assert "search_files" in client.instructions[0]
    assert client.previous_response_ids == [None]
    assert printed[0] == "status: llm_wait"
    assert printed[1].startswith("tool: edit_file")
    assert printed[2].startswith("tool_result: edit_file")


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
    agent = CodingAgent(
        client=FailingClient(),
        model="test-model",
        registry=build_tool_registry(tmp_path),
    )

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
    agent = CodingAgent(
        client=LoopingClient(),
        model="test-model",
        registry=build_tool_registry(tmp_path),
    )

    answer = agent.ask("keep looping")

    assert answer == "Stopped because the tool loop exceeded the safety limit."
