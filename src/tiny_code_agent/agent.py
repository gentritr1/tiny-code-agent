from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from .tools import Tool, dispatch_tool


SYSTEM_PROMPT = """You are Tiny Code Agent, a careful beginner-friendly coding assistant.
You can inspect and edit files only through the provided tools.
Prefer small, exact edits. If an edit fails, explain the failure instead of guessing.
After using tools, summarize what changed and mention any files touched."""


class ResponseClient(Protocol):
    def create_response(
        self,
        *,
        model: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        instructions: str,
    ) -> Any:
        ...


class OpenAIResponseClient:
    def __init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI()

    def create_response(
        self,
        *,
        model: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        instructions: str,
    ) -> Any:
        return self._client.responses.create(
            model=model,
            input=input_items,
            tools=tools,
            instructions=instructions,
        )


def get_output_text(response: Any) -> str:
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


def get_function_calls(response: Any) -> list[Any]:
    return [
        item
        for item in getattr(response, "output", []) or []
        if getattr(item, "type", None) == "function_call"
    ]


class CodingAgent:
    def __init__(
        self,
        *,
        client: ResponseClient,
        model: str,
        registry: dict[str, Tool],
        printer: Callable[[str], None] | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.registry = registry
        self.messages: list[dict[str, Any]] = []
        self.printer = printer or (lambda message: None)

    def ask(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(12):
            response = self.client.create_response(
                model=self.model,
                input_items=self.messages,
                tools=[tool.schema() for tool in self.registry.values()],
                instructions=SYSTEM_PROMPT,
            )
            calls = get_function_calls(response)
            if not calls:
                answer = get_output_text(response)
                self.messages.append({"role": "assistant", "content": answer})
                return answer

            self.messages.extend(_response_output_as_input(response))
            for call in calls:
                name = str(getattr(call, "name"))
                raw_arguments = getattr(call, "arguments", "{}") or "{}"
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError as exc:
                    result = {"ok": False, "error": "invalid_json", "message": str(exc)}
                else:
                    self.printer(f"tool: {name} {json.dumps(arguments, ensure_ascii=False)}")
                    result = dispatch_tool(self.registry, name, arguments)

                self.messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": getattr(call, "call_id"),
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

        return "Stopped because the tool loop exceeded the safety limit."


def _response_output_as_input(response: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in getattr(response, "output", []) or []:
        if hasattr(item, "model_dump"):
            items.append(item.model_dump())
        elif isinstance(item, dict):
            items.append(item)
    return items
