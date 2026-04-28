from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .llm import LLMClient, ToolCallResult
from .tools import Tool, dispatch_tool


SYSTEM_PROMPT = """You are Tiny Code Agent, a careful beginner-friendly coding assistant.
You can inspect and edit files only through the provided tools.
Prefer small, exact edits. If an edit fails, explain the failure instead of guessing.
After using tools, summarize what changed and mention any files touched."""


class CodingAgent:
    def __init__(
        self,
        *,
        client: LLMClient,
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
        history_start = len(self.messages)
        self.messages.append({"role": "user", "content": user_message})

        try:
            for _ in range(12):
                turn = self.client.complete(
                    model=self.model,
                    messages=self.messages,
                    tools=list(self.registry.values()),
                    instructions=SYSTEM_PROMPT,
                )
                self.messages.extend(turn.messages)

                if not turn.tool_calls:
                    return turn.text

                for call in turn.tool_calls:
                    self.printer(
                        f"tool: {call.name} {json.dumps(call.arguments, ensure_ascii=False)}"
                    )
                    result = dispatch_tool(self.registry, call.name, call.arguments)
                    self.messages.append(
                        self.client.tool_result_message(
                            ToolCallResult(call_id=call.id, name=call.name, output=result)
                        )
                    )
        except Exception:
            del self.messages[history_start:]
            raise

        return "Stopped because the tool loop exceeded the safety limit."
