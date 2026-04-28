from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tiny_code_agent.agent import CodingAgent
from tiny_code_agent.tools import build_tool_registry


@dataclass
class FakeFunctionCall:
    name: str
    arguments: str
    call_id: str = "call_1"
    type: str = "function_call"

    def model_dump(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "arguments": self.arguments,
            "call_id": self.call_id,
        }


@dataclass
class FakeResponse:
    output: list[Any]
    output_text: str = ""


class FakeClient:
    def __init__(self) -> None:
        self.inputs: list[list[dict[str, Any]]] = []

    def create_response(
        self,
        *,
        model: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        instructions: str,
    ) -> FakeResponse:
        self.inputs.append(list(input_items))
        if len(self.inputs) == 1:
            return FakeResponse(
                output=[
                    FakeFunctionCall(
                        name="edit_file",
                        arguments=json.dumps(
                            {"path": "hello.py", "old_str": "", "new_str": "print('hi')\n"}
                        ),
                    )
                ]
            )
        return FakeResponse(output=[], output_text="Created hello.py.")


def test_agent_executes_tool_and_returns_final_answer(tmp_path: Path) -> None:
    client = FakeClient()
    agent = CodingAgent(client=client, model="test-model", registry=build_tool_registry(tmp_path))

    answer = agent.ask("create hello.py")

    assert answer == "Created hello.py."
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "print('hi')\n"
    assert client.inputs[-1][-1]["type"] == "function_call_output"
    assert "created_file" in client.inputs[-1][-1]["output"]
