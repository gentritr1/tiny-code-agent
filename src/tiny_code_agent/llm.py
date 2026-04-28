from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .tools import Tool


Message = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AssistantTurn:
    messages: list[Message]
    text: str
    tool_calls: list[ToolCall]


@dataclass(frozen=True)
class ToolCallResult:
    call_id: str
    name: str
    output: dict[str, Any]


class LLMClient(Protocol):
    provider_name: str

    def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        instructions: str,
    ) -> AssistantTurn:
        ...

    def tool_result_message(self, result: ToolCallResult) -> Message:
        ...
