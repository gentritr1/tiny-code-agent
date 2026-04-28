from __future__ import annotations

import json
from typing import Any

from ..llm import AssistantTurn, Message, ToolCall, ToolCallResult
from ..tools import Tool


class OpenAIClient:
    provider_name = "openai"

    def __init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI()

    def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        tools: list[Tool],
        instructions: str,
    ) -> AssistantTurn:
        response = self._client.responses.create(
            model=model,
            input=messages,
            tools=[tool.schema() for tool in tools],
            instructions=instructions,
        )
        output_items = _response_output_as_messages(response)
        return AssistantTurn(
            messages=output_items,
            text=_get_output_text(response),
            tool_calls=_get_tool_calls(response),
        )

    def tool_result_message(self, result: ToolCallResult) -> Message:
        return {
            "type": "function_call_output",
            "call_id": result.call_id,
            "output": json.dumps(result.output, ensure_ascii=False),
        }


def _get_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return str(text)

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) in {"output_text", "text"}:
                value = getattr(content, "text", "")
                if value:
                    parts.append(str(value))
    return "\n".join(parts)


def _get_tool_calls(response: Any) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "function_call":
            continue
        raw_arguments = getattr(item, "arguments", "{}") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            arguments = {"_invalid_json": raw_arguments, "_error": str(exc)}
        calls.append(
            ToolCall(
                id=str(getattr(item, "call_id")),
                name=str(getattr(item, "name")),
                arguments=arguments,
            )
        )
    return calls


def _response_output_as_messages(response: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in getattr(response, "output", []) or []:
        if hasattr(item, "model_dump"):
            items.append(item.model_dump())
        elif isinstance(item, dict):
            items.append(item)
    return items
