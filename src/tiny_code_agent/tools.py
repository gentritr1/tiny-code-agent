from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ToolResult = dict[str, Any]
ToolHandler = Callable[..., ToolResult]


class WorkspaceError(ValueError):
    """Raised when a requested path escapes the workspace."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": True,
        }


def resolve_workspace_path(workspace: Path, path: str) -> Path:
    root = workspace.expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()

    if resolved != root and root not in resolved.parents:
        raise WorkspaceError(f"path escapes workspace: {path}")
    return resolved


def list_files(workspace: Path, path: str = ".") -> ToolResult:
    try:
        target = resolve_workspace_path(workspace, path)
        if not target.exists():
            return {"ok": False, "error": "path_not_found", "path": str(target)}
        if not target.is_dir():
            return {"ok": False, "error": "not_a_directory", "path": str(target)}

        files = [
            {"filename": item.name, "type": "file" if item.is_file() else "dir"}
            for item in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        ]
        return {"ok": True, "path": str(target), "files": files}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def read_file(workspace: Path, path: str) -> ToolResult:
    try:
        target = resolve_workspace_path(workspace, path)
        if not target.exists():
            return {"ok": False, "error": "file_not_found", "path": str(target)}
        if not target.is_file():
            return {"ok": False, "error": "not_a_file", "path": str(target)}
        return {"ok": True, "path": str(target), "content": target.read_text(encoding="utf-8")}
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def edit_file(workspace: Path, path: str, old_str: str, new_str: str) -> ToolResult:
    try:
        target = resolve_workspace_path(workspace, path)
        if old_str == "":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_str, encoding="utf-8")
            return {"ok": True, "path": str(target), "action": "created_file"}

        if not target.exists():
            return {"ok": False, "error": "file_not_found", "path": str(target)}
        if not target.is_file():
            return {"ok": False, "error": "not_a_file", "path": str(target)}

        original = target.read_text(encoding="utf-8")
        if old_str not in original:
            return {"ok": False, "error": "old_str_not_found", "path": str(target)}

        edited = original.replace(old_str, new_str, 1)
        target.write_text(edited, encoding="utf-8")
        return {"ok": True, "path": str(target), "action": "edited"}
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def build_tool_registry(workspace: Path) -> dict[str, Tool]:
    string_schema = {"type": "string"}
    return {
        "list_files": Tool(
            name="list_files",
            description="List files and directories inside a workspace directory.",
            parameters={
                "type": "object",
                "properties": {"path": string_schema},
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=lambda path=".": list_files(workspace, path),
        ),
        "read_file": Tool(
            name="read_file",
            description="Read a UTF-8 text file inside the workspace.",
            parameters={
                "type": "object",
                "properties": {"path": string_schema},
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=lambda path: read_file(workspace, path),
        ),
        "edit_file": Tool(
            name="edit_file",
            description=(
                "Create or edit a UTF-8 text file inside the workspace. "
                "When old_str is empty, create or overwrite the file with new_str. "
                "Otherwise replace the first exact occurrence of old_str with new_str."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": string_schema,
                    "old_str": string_schema,
                    "new_str": string_schema,
                },
                "required": ["path", "old_str", "new_str"],
                "additionalProperties": False,
            },
            handler=lambda path, old_str, new_str: edit_file(workspace, path, old_str, new_str),
        ),
    }


def dispatch_tool(registry: dict[str, Tool], name: str, arguments: dict[str, Any]) -> ToolResult:
    tool = registry.get(name)
    if tool is None:
        return {"ok": False, "error": "unknown_tool", "tool": name}
    try:
        return tool.handler(**arguments)
    except TypeError as exc:
        return {"ok": False, "error": "invalid_arguments", "tool": name, "message": str(exc)}
