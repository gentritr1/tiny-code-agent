from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .llm import LLMClient, ToolCallResult
from .tools import Tool, dispatch_tool


WRITE_TOOLS = {"edit_file", "append_file", "insert_after", "insert_before"}


SYSTEM_PROMPT = """You are Tiny Code Agent, a careful beginner-friendly coding assistant.
You can inspect and edit files only through the provided tools.
Prefer small, exact edits. If an edit fails, explain the failure instead of guessing.
Use list_tree for a bounded project overview and search_files to find exact
text or symbols before reading many files.
When changing files, use preview_edit_file first when practical so the user can
learn from the diff before the write.
Use preview_append_file before append_file, preview_insert_after before
insert_after, and preview_insert_before before insert_before when practical.
Use append_file when the user wants to add content to the end of an existing
file.
Use insert_after when the user wants to add content after a specific existing
line or block.
Use insert_before when the user wants to add content before a specific existing
line or block.
If any write tool returns edit_rejected or another write error, do not retry
the write. Tell the user no changes were made and wait for a new request.
After a successful write tool call, stop. The user can send another request if
they want more changes.
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
        current_input: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        previous_response_id: str | None = None
        self.messages.extend(current_input)

        try:
            for _ in range(12):
                self.printer("status: llm_wait")
                turn = self.client.complete(
                    model=self.model,
                    messages=current_input,
                    tools=list(self.registry.values()),
                    instructions=SYSTEM_PROMPT,
                    previous_response_id=previous_response_id,
                )
                previous_response_id = turn.response_id
                self.messages.extend(turn.messages)

                if not turn.tool_calls:
                    return turn.text

                next_input: list[dict[str, Any]] = []
                for call in turn.tool_calls:
                    self.printer(
                        f"tool: {call.name} {json.dumps(call.arguments, ensure_ascii=False)}"
                    )
                    result = dispatch_tool(self.registry, call.name, call.arguments)
                    self.printer(
                        f"tool_result: {call.name} {json.dumps(result, ensure_ascii=False)}"
                    )
                    tool_message = self.client.tool_result_message(
                        ToolCallResult(call_id=call.id, name=call.name, output=result)
                    )
                    self.messages.append(tool_message)
                    next_input.append(tool_message)
                    if result.get("error") == "edit_rejected":
                        return (
                            "Edit rejected. No changes were made. "
                            "Send a new request to try again."
                        )
                    if call.name in WRITE_TOOLS and result.get("ok") is False:
                        return (
                            f"Write failed with {result.get('error', 'unknown')}. "
                            "No changes were made."
                        )
                    if call.name in WRITE_TOOLS and result.get("ok") is True:
                        action = result.get("action", call.name)
                        path = call.arguments.get("path", result.get("path", "the file"))
                        return f"Applied {action} to {path}. No further changes were made."
                current_input = next_input
        except Exception:
            del self.messages[history_start:]
            raise

        return "Stopped because the tool loop exceeded the safety limit."
