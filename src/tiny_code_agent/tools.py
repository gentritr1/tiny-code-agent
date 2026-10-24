from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ToolResult = dict[str, Any]
ToolHandler = Callable[..., ToolResult]
EditConfirmation = Callable[[Path, str], bool]
EDIT_REJECTED_MESSAGE = "User rejected the edit. Do not retry without a new user request."


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
            for item in sorted(
                target.iterdir(),
                key=lambda item: (not item.is_dir(), item.name.lower()),
            )
        ]
        return {"ok": True, "path": str(target), "files": files}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def list_tree(
    workspace: Path,
    path: str = ".",
    max_depth: int = 2,
    max_entries: int = 100,
) -> ToolResult:
    try:
        root = resolve_workspace_path(workspace, ".")
        target = resolve_workspace_path(workspace, path)
        if not target.exists():
            return {"ok": False, "error": "path_not_found", "path": str(target)}
        if not target.is_dir():
            return {"ok": False, "error": "not_a_directory", "path": str(target)}

        entries: list[dict[str, str]] = []

        def walk(directory: Path, depth: int) -> None:
            if depth > max_depth or len(entries) >= max_entries:
                return
            for item in sorted(
                directory.iterdir(),
                key=lambda item: (not item.is_dir(), item.name.lower()),
            ):
                if item.name in {".git", ".venv", "__pycache__", ".pytest_cache"}:
                    continue
                entry_type = "file" if item.is_file() else "dir"
                entries.append({"path": item.relative_to(root).as_posix(), "type": entry_type})
                if len(entries) >= max_entries:
                    return
                if item.is_dir():
                    walk(item, depth + 1)

        walk(target, 1)
        return {
            "ok": True,
            "path": str(target),
            "entries": entries,
            "truncated": len(entries) >= max_entries,
        }
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def search_files(
    workspace: Path,
    query: str,
    path: str = ".",
    max_results: int = 20,
) -> ToolResult:
    try:
        root = resolve_workspace_path(workspace, ".")
        target = resolve_workspace_path(workspace, path)
        if not target.exists():
            return {"ok": False, "error": "path_not_found", "path": str(target)}
        if not query:
            return {"ok": False, "error": "empty_query"}

        matches: list[dict[str, Any]] = []
        candidates = [target] if target.is_file() else sorted(target.rglob("*"))
        for file_path in candidates:
            if len(matches) >= max_results:
                break
            if any(
                part in {".git", ".venv", "__pycache__", ".pytest_cache"}
                for part in file_path.parts
            ):
                continue
            if not file_path.is_file():
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if query in line:
                    matches.append(
                        {
                            "path": file_path.relative_to(root).as_posix(),
                            "line": line_number,
                            "text": line.strip(),
                        }
                    )
                    if len(matches) >= max_results:
                        break

        return {
            "ok": True,
            "path": str(target),
            "query": query,
            "matches": matches,
            "truncated": len(matches) >= max_results,
        }
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


def _diff(path: str, original: str, edited: str) -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            edited.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _edit_rejected(target: Path) -> ToolResult:
    return {
        "ok": False,
        "error": "edit_rejected",
        "path": str(target),
        "message": EDIT_REJECTED_MESSAGE,
    }


def _read_existing_text(workspace: Path, path: str) -> tuple[Path, str] | ToolResult:
    target = resolve_workspace_path(workspace, path)
    if not target.exists():
        return {"ok": False, "error": "file_not_found", "path": str(target)}
    if not target.is_file():
        return {"ok": False, "error": "not_a_file", "path": str(target)}
    return target, target.read_text(encoding="utf-8")


def edit_file(
    workspace: Path,
    path: str,
    old_str: str,
    new_str: str,
    *,
    confirm: EditConfirmation | None = None,
) -> ToolResult:
    try:
        target = resolve_workspace_path(workspace, path)
        if old_str == "":
            if confirm and not confirm(target, "created_file"):
                return _edit_rejected(target)
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
        if confirm and not confirm(target, "edited"):
            return _edit_rejected(target)
        target.write_text(edited, encoding="utf-8")
        return {"ok": True, "path": str(target), "action": "edited"}
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def preview_edit_file(workspace: Path, path: str, old_str: str, new_str: str) -> ToolResult:
    try:
        target = resolve_workspace_path(workspace, path)
        if old_str == "":
            original = target.read_text(encoding="utf-8") if target.exists() else ""
            action = "previewed_overwrite" if target.exists() else "previewed_create"
            diff = _diff(path, original, new_str)
            return {"ok": True, "path": str(target), "action": action, "diff": diff}

        if not target.exists():
            return {"ok": False, "error": "file_not_found", "path": str(target)}
        if not target.is_file():
            return {"ok": False, "error": "not_a_file", "path": str(target)}

        original = target.read_text(encoding="utf-8")
        if old_str not in original:
            return {"ok": False, "error": "old_str_not_found", "path": str(target)}

        edited = original.replace(old_str, new_str, 1)
        diff = _diff(path, original, edited)
        return {"ok": True, "path": str(target), "action": "previewed_edit", "diff": diff}
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def append_file(
    workspace: Path,
    path: str,
    text: str,
    *,
    confirm: EditConfirmation | None = None,
) -> ToolResult:
    try:
        target = resolve_workspace_path(workspace, path)
        if not target.exists():
            return {"ok": False, "error": "file_not_found", "path": str(target)}
        if not target.is_file():
            return {"ok": False, "error": "not_a_file", "path": str(target)}

        target.read_text(encoding="utf-8")
        if confirm and not confirm(target, "appended"):
            return _edit_rejected(target)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(text)
        return {"ok": True, "path": str(target), "action": "appended"}
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def preview_append_file(workspace: Path, path: str, text: str) -> ToolResult:
    try:
        loaded = _read_existing_text(workspace, path)
        if isinstance(loaded, dict):
            return loaded
        target, original = loaded
        return {
            "ok": True,
            "path": str(target),
            "action": "previewed_append",
            "diff": _diff(path, original, original + text),
        }
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def insert_after(
    workspace: Path,
    path: str,
    anchor: str,
    text: str,
    *,
    confirm: EditConfirmation | None = None,
) -> ToolResult:
    try:
        target = resolve_workspace_path(workspace, path)
        if not target.exists():
            return {"ok": False, "error": "file_not_found", "path": str(target)}
        if not target.is_file():
            return {"ok": False, "error": "not_a_file", "path": str(target)}

        original = target.read_text(encoding="utf-8")
        if anchor not in original:
            return {"ok": False, "error": "anchor_not_found", "path": str(target)}

        inserted = original.replace(anchor, anchor + text, 1)
        if confirm and not confirm(target, "inserted_after"):
            return _edit_rejected(target)
        target.write_text(inserted, encoding="utf-8")
        return {"ok": True, "path": str(target), "action": "inserted_after"}
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def preview_insert_after(workspace: Path, path: str, anchor: str, text: str) -> ToolResult:
    try:
        loaded = _read_existing_text(workspace, path)
        if isinstance(loaded, dict):
            return loaded
        target, original = loaded
        if anchor not in original:
            return {"ok": False, "error": "anchor_not_found", "path": str(target)}
        inserted = original.replace(anchor, anchor + text, 1)
        return {
            "ok": True,
            "path": str(target),
            "action": "previewed_insert_after",
            "diff": _diff(path, original, inserted),
        }
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def insert_before(
    workspace: Path,
    path: str,
    anchor: str,
    text: str,
    *,
    confirm: EditConfirmation | None = None,
) -> ToolResult:
    try:
        loaded = _read_existing_text(workspace, path)
        if isinstance(loaded, dict):
            return loaded
        target, original = loaded
        if anchor not in original:
            return {"ok": False, "error": "anchor_not_found", "path": str(target)}

        inserted = original.replace(anchor, text + anchor, 1)
        if confirm and not confirm(target, "inserted_before"):
            return _edit_rejected(target)
        target.write_text(inserted, encoding="utf-8")
        return {"ok": True, "path": str(target), "action": "inserted_before"}
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def preview_insert_before(workspace: Path, path: str, anchor: str, text: str) -> ToolResult:
    try:
        loaded = _read_existing_text(workspace, path)
        if isinstance(loaded, dict):
            return loaded
        target, original = loaded
        if anchor not in original:
            return {"ok": False, "error": "anchor_not_found", "path": str(target)}
        inserted = original.replace(anchor, text + anchor, 1)
        return {
            "ok": True,
            "path": str(target),
            "action": "previewed_insert_before",
            "diff": _diff(path, original, inserted),
        }
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode_error", "message": "file is not valid UTF-8"}
    except WorkspaceError as exc:
        return {"ok": False, "error": "workspace_violation", "message": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": "os_error", "message": str(exc)}


def build_tool_registry(
    workspace: Path,
    *,
    confirm_edit: EditConfirmation | None = None,
) -> dict[str, Tool]:
    string_schema = {"type": "string"}
    integer_schema = {"type": "integer"}
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
        "list_tree": Tool(
            name="list_tree",
            description=(
                "List a bounded recursive tree of files and directories inside the workspace."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": string_schema,
                    "max_depth": integer_schema,
                    "max_entries": integer_schema,
                },
                "required": ["path", "max_depth", "max_entries"],
                "additionalProperties": False,
            },
            handler=lambda path=".", max_depth=2, max_entries=100: list_tree(
                workspace,
                path,
                max_depth,
                max_entries,
            ),
        ),
        "search_files": Tool(
            name="search_files",
            description=(
                "Search UTF-8 files inside the workspace for exact text matches. "
                "Returns matching path, line number, and line text."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": string_schema,
                    "path": string_schema,
                    "max_results": integer_schema,
                },
                "required": ["query", "path", "max_results"],
                "additionalProperties": False,
            },
            handler=lambda query, path=".", max_results=20: search_files(
                workspace,
                query,
                path,
                max_results,
            ),
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
            handler=lambda path, old_str, new_str: edit_file(
                workspace,
                path,
                old_str,
                new_str,
                confirm=confirm_edit,
            ),
        ),
        "preview_edit_file": Tool(
            name="preview_edit_file",
            description=(
                "Preview an edit to a UTF-8 text file inside the workspace without writing it. "
                "Returns a unified diff for replacing the first exact occurrence of old_str "
                "with new_str."
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
            handler=lambda path, old_str, new_str: preview_edit_file(
                workspace, path, old_str, new_str
            ),
        ),
        "append_file": Tool(
            name="append_file",
            description=(
                "Append text to an existing UTF-8 text file inside the workspace. "
                "Use this for adding content to the end of a file without replacing text."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": string_schema,
                    "text": string_schema,
                },
                "required": ["path", "text"],
                "additionalProperties": False,
            },
            handler=lambda path, text: append_file(
                workspace,
                path,
                text,
                confirm=confirm_edit,
            ),
        ),
        "preview_append_file": Tool(
            name="preview_append_file",
            description=(
                "Preview appending text to an existing UTF-8 text file inside the workspace "
                "without writing it. Returns a unified diff."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": string_schema,
                    "text": string_schema,
                },
                "required": ["path", "text"],
                "additionalProperties": False,
            },
            handler=lambda path, text: preview_append_file(workspace, path, text),
        ),
        "insert_after": Tool(
            name="insert_after",
            description=(
                "Insert text after the first exact anchor match in an existing UTF-8 text file "
                "inside the workspace."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": string_schema,
                    "anchor": string_schema,
                    "text": string_schema,
                },
                "required": ["path", "anchor", "text"],
                "additionalProperties": False,
            },
            handler=lambda path, anchor, text: insert_after(
                workspace,
                path,
                anchor,
                text,
                confirm=confirm_edit,
            ),
        ),
        "preview_insert_after": Tool(
            name="preview_insert_after",
            description=(
                "Preview inserting text after the first exact anchor match in an existing "
                "UTF-8 text file inside the workspace without writing it. Returns a unified diff."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": string_schema,
                    "anchor": string_schema,
                    "text": string_schema,
                },
                "required": ["path", "anchor", "text"],
                "additionalProperties": False,
            },
            handler=lambda path, anchor, text: preview_insert_after(
                workspace,
                path,
                anchor,
                text,
            ),
        ),
        "insert_before": Tool(
            name="insert_before",
            description=(
                "Insert text before the first exact anchor match in an existing UTF-8 text file "
                "inside the workspace."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": string_schema,
                    "anchor": string_schema,
                    "text": string_schema,
                },
                "required": ["path", "anchor", "text"],
                "additionalProperties": False,
            },
            handler=lambda path, anchor, text: insert_before(
                workspace,
                path,
                anchor,
                text,
                confirm=confirm_edit,
            ),
        ),
        "preview_insert_before": Tool(
            name="preview_insert_before",
            description=(
                "Preview inserting text before the first exact anchor match in an existing "
                "UTF-8 text file inside the workspace without writing it. Returns a unified diff."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": string_schema,
                    "anchor": string_schema,
                    "text": string_schema,
                },
                "required": ["path", "anchor", "text"],
                "additionalProperties": False,
            },
            handler=lambda path, anchor, text: preview_insert_before(
                workspace,
                path,
                anchor,
                text,
            ),
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
