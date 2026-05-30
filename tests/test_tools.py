from pathlib import Path
import os

from tiny_code_agent.tools import (
    append_file,
    dispatch_tool,
    edit_file,
    insert_before,
    insert_after,
    list_files,
    list_tree,
    preview_append_file,
    preview_edit_file,
    preview_insert_after,
    preview_insert_before,
    read_file,
    resolve_workspace_path,
    search_files,
)
from tiny_code_agent.tools import build_tool_registry, WorkspaceError
from tiny_code_agent.tools import Tool


def test_resolve_path_rejects_parent_escape(tmp_path: Path) -> None:
    try:
        resolve_workspace_path(tmp_path, "../secret.txt")
    except WorkspaceError:
        return
    raise AssertionError("expected WorkspaceError")


def test_list_files_returns_metadata(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")

    result = list_files(tmp_path, ".")

    assert result["ok"] is True
    assert {"filename": "pkg", "type": "dir"} in result["files"]
    assert {"filename": "main.py", "type": "file"} in result["files"]


def test_list_files_reports_missing_path(tmp_path: Path) -> None:
    result = list_files(tmp_path, "missing")

    assert result["ok"] is False
    assert result["error"] == "path_not_found"


def test_list_files_reports_not_a_directory(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")

    result = list_files(tmp_path, "main.py")

    assert result["ok"] is False
    assert result["error"] == "not_a_directory"


def test_list_files_rejects_workspace_escape(tmp_path: Path) -> None:
    result = list_files(tmp_path, "../secret")

    assert result["ok"] is False
    assert result["error"] == "workspace_violation"


def test_list_files_reports_os_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "iterdir", lambda self: (_ for _ in ()).throw(OSError("boom")))

    result = list_files(tmp_path, ".")

    assert result["ok"] is False
    assert result["error"] == "os_error"


def test_list_tree_returns_bounded_nested_paths(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "main.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo", encoding="utf-8")

    result = list_tree(tmp_path, ".", max_depth=2, max_entries=10)

    assert result["ok"] is True
    assert {"path": "README.md", "type": "file"} in result["entries"]
    assert {"path": "pkg", "type": "dir"} in result["entries"]
    assert {"path": "pkg/main.py", "type": "file"} in result["entries"]


def test_search_files_finds_text_matches(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("nothing here\n", encoding="utf-8")

    result = search_files(tmp_path, "hello")

    assert result["ok"] is True
    assert result["matches"] == [{"path": "app.py", "line": 1, "text": "def hello():"}]


def test_search_files_can_search_one_file(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    result = search_files(tmp_path, "hello", path="app.py")

    assert result["ok"] is True
    assert result["matches"] == [{"path": "app.py", "line": 1, "text": "def hello():"}]


def test_read_file_returns_content(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("hello", encoding="utf-8")

    result = read_file(tmp_path, "main.py")

    assert result["ok"] is True
    assert result["content"] == "hello"


def test_read_file_rejects_workspace_escape(tmp_path: Path) -> None:
    result = read_file(tmp_path, "../secret.txt")

    assert result["ok"] is False
    assert result["error"] == "workspace_violation"


def test_read_file_reports_missing_file(tmp_path: Path) -> None:
    result = read_file(tmp_path, "missing.py")

    assert result["ok"] is False
    assert result["error"] == "file_not_found"


def test_read_file_reports_not_a_file(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()

    result = read_file(tmp_path, "pkg")

    assert result["ok"] is False
    assert result["error"] == "not_a_file"


def test_read_file_reports_decode_error(tmp_path: Path) -> None:
    (tmp_path / "data.bin").write_bytes(b"\xff")

    result = read_file(tmp_path, "data.bin")

    assert result["ok"] is False
    assert result["error"] == "decode_error"


def test_read_file_reports_os_error(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text("hello", encoding="utf-8")
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, encoding="utf-8": (_ for _ in ()).throw(OSError("boom")),
    )

    result = read_file(tmp_path, "main.py")

    assert result["ok"] is False
    assert result["error"] == "os_error"


def test_edit_file_creates_file(tmp_path: Path) -> None:
    result = edit_file(tmp_path, "hello.py", "", "print('hello')\n")

    assert result["ok"] is True
    assert result["action"] == "created_file"
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "print('hello')\n"


def test_edit_file_replaces_first_exact_match(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("x = 1\nx = 1\n", encoding="utf-8")

    result = edit_file(tmp_path, "hello.py", "x = 1", "x = 2")

    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == "x = 2\nx = 1\n"


def test_edit_file_can_be_rejected_by_confirmation(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = edit_file(
        tmp_path,
        "hello.py",
        "x = 1",
        "x = 2",
        confirm=lambda path, action: False,
    )

    assert result["ok"] is False
    assert result["error"] == "edit_rejected"
    assert result["message"] == "User rejected the edit. Do not retry without a new user request."
    assert target.read_text(encoding="utf-8") == "x = 1\n"


def test_preview_edit_file_returns_diff_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("x = 1\nx = 1\n", encoding="utf-8")

    result = preview_edit_file(tmp_path, "hello.py", "x = 1", "x = 2")

    assert result["ok"] is True
    assert result["action"] == "previewed_edit"
    assert "-x = 1" in result["diff"]
    assert "+x = 2" in result["diff"]
    assert target.read_text(encoding="utf-8") == "x = 1\nx = 1\n"


def test_preview_edit_file_can_preview_new_file(tmp_path: Path) -> None:
    result = preview_edit_file(tmp_path, "hello.py", "", "print('hello')\n")

    assert result["ok"] is True
    assert result["action"] == "previewed_create"
    assert "+print('hello')" in result["diff"]
    assert not (tmp_path / "hello.py").exists()


def test_edit_file_reports_missing_old_str(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("x = 1\n", encoding="utf-8")

    result = edit_file(tmp_path, "hello.py", "missing", "x = 2")

    assert result["ok"] is False
    assert result["error"] == "old_str_not_found"


def test_edit_file_reports_missing_file_for_replace(tmp_path: Path) -> None:
    result = edit_file(tmp_path, "missing.py", "x", "y")

    assert result["ok"] is False
    assert result["error"] == "file_not_found"


def test_edit_file_reports_not_a_file(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()

    result = edit_file(tmp_path, "pkg", "x", "y")

    assert result["ok"] is False
    assert result["error"] == "not_a_file"


def test_edit_file_reports_decode_error(tmp_path: Path) -> None:
    (tmp_path / "data.bin").write_bytes(b"\xff")

    result = edit_file(tmp_path, "data.bin", "x", "y")

    assert result["ok"] is False
    assert result["error"] == "decode_error"


def test_edit_file_rejects_workspace_escape(tmp_path: Path) -> None:
    result = edit_file(tmp_path, "../secret.txt", "", "hello")

    assert result["ok"] is False
    assert result["error"] == "workspace_violation"


def test_edit_file_reports_os_error(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text("hello", encoding="utf-8")
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda self, text, encoding="utf-8": (_ for _ in ()).throw(OSError("boom")),
    )

    result = edit_file(tmp_path, "main.py", "hello", "bye")

    assert result["ok"] is False
    assert result["error"] == "os_error"


def test_append_file_adds_text_to_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\n", encoding="utf-8")

    result = append_file(tmp_path, "notes.txt", "two\n")

    assert result["ok"] is True
    assert result["action"] == "appended"
    assert target.read_text(encoding="utf-8") == "one\ntwo\n"


def test_append_file_reports_missing_file(tmp_path: Path) -> None:
    result = append_file(tmp_path, "missing.txt", "hello\n")

    assert result["ok"] is False
    assert result["error"] == "file_not_found"


def test_append_file_can_be_rejected_by_confirmation(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\n", encoding="utf-8")

    result = append_file(tmp_path, "notes.txt", "two\n", confirm=lambda path, action: False)

    assert result["ok"] is False
    assert result["error"] == "edit_rejected"
    assert target.read_text(encoding="utf-8") == "one\n"


def test_preview_append_file_returns_diff_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\n", encoding="utf-8")

    result = preview_append_file(tmp_path, "notes.txt", "two\n")

    assert result["ok"] is True
    assert result["action"] == "previewed_append"
    assert "+two" in result["diff"]
    assert target.read_text(encoding="utf-8") == "one\n"


def test_insert_after_adds_text_after_anchor(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    result = insert_after(tmp_path, "hello.py", "def hello():\n", "    # greeting\n")

    assert result["ok"] is True
    assert result["action"] == "inserted_after"
    assert target.read_text(encoding="utf-8") == "def hello():\n    # greeting\n    return 'hi'\n"


def test_insert_after_reports_missing_anchor(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    result = insert_after(tmp_path, "hello.py", "missing", "new text")

    assert result["ok"] is False
    assert result["error"] == "anchor_not_found"


def test_insert_after_can_be_rejected_by_confirmation(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    result = insert_after(
        tmp_path,
        "hello.py",
        "def hello():\n",
        "    # greeting\n",
        confirm=lambda path, action: False,
    )

    assert result["ok"] is False
    assert result["error"] == "edit_rejected"
    assert target.read_text(encoding="utf-8") == "def hello():\n    return 'hi'\n"


def test_preview_insert_after_returns_diff_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    result = preview_insert_after(tmp_path, "hello.py", "def hello():\n", "    # greeting\n")

    assert result["ok"] is True
    assert result["action"] == "previewed_insert_after"
    assert "+    # greeting" in result["diff"]
    assert target.read_text(encoding="utf-8") == "def hello():\n    return 'hi'\n"


def test_insert_before_adds_text_before_anchor(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    result = insert_before(tmp_path, "hello.py", "    return 'hi'\n", "    # greeting\n")

    assert result["ok"] is True
    assert result["action"] == "inserted_before"
    assert target.read_text(encoding="utf-8") == "def hello():\n    # greeting\n    return 'hi'\n"


def test_preview_insert_before_returns_diff_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    result = preview_insert_before(tmp_path, "hello.py", "    return 'hi'\n", "    # greeting\n")

    assert result["ok"] is True
    assert result["action"] == "previewed_insert_before"
    assert "+    # greeting" in result["diff"]
    assert target.read_text(encoding="utf-8") == "def hello():\n    return 'hi'\n"


def test_tool_schema_includes_strict_flag() -> None:
    tool = Tool(
        name="demo",
        description="desc",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        handler=lambda: {"ok": True},
    )

    assert tool.schema()["strict"] is True


def test_dispatch_tool_reports_unknown_tool(tmp_path: Path) -> None:
    registry = build_tool_registry(tmp_path)

    result = dispatch_tool(registry, "missing_tool", {})

    assert result["ok"] is False
    assert result["error"] == "unknown_tool"


def test_dispatch_tool_reports_invalid_arguments(tmp_path: Path) -> None:
    registry = build_tool_registry(tmp_path)

    result = dispatch_tool(registry, "read_file", {})

    assert result["ok"] is False
    assert result["error"] == "invalid_arguments"


def test_tool_registry_can_confirm_edit_file(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("x = 1\n", encoding="utf-8")
    confirmations: list[tuple[Path, str]] = []
    registry = build_tool_registry(
        tmp_path,
        confirm_edit=lambda path, action: confirmations.append((path, action)) or False,
    )

    result = dispatch_tool(
        registry,
        "edit_file",
        {"path": "hello.py", "old_str": "x = 1", "new_str": "x = 2"},
    )

    assert result["ok"] is False
    assert result["error"] == "edit_rejected"
    assert confirmations == [(target, "edited")]


def test_tool_registry_exposes_append_file(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\n", encoding="utf-8")
    registry = build_tool_registry(tmp_path)

    result = dispatch_tool(registry, "append_file", {"path": "notes.txt", "text": "two\n"})

    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == "one\ntwo\n"


def test_tool_registry_exposes_insert_after(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    registry = build_tool_registry(tmp_path)

    result = dispatch_tool(
        registry,
        "insert_after",
        {"path": "hello.py", "anchor": "def hello():\n", "text": "    # greeting\n"},
    )

    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == "def hello():\n    # greeting\n    return 'hi'\n"


def test_tool_registry_exposes_insert_before_and_previews(tmp_path: Path) -> None:
    target = tmp_path / "hello.py"
    target.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    registry = build_tool_registry(tmp_path)

    preview = dispatch_tool(
        registry,
        "preview_insert_before",
        {"path": "hello.py", "anchor": "    return 'hi'\n", "text": "    # greeting\n"},
    )
    result = dispatch_tool(
        registry,
        "insert_before",
        {"path": "hello.py", "anchor": "    return 'hi'\n", "text": "    # greeting\n"},
    )

    assert preview["ok"] is True
    assert preview["action"] == "previewed_insert_before"
    assert result["ok"] is True
    assert target.read_text(encoding="utf-8") == "def hello():\n    # greeting\n    return 'hi'\n"


def test_tool_registry_exposes_read_only_discovery_tools(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    registry = build_tool_registry(tmp_path)

    tree = dispatch_tool(registry, "list_tree", {"path": ".", "max_depth": 1, "max_entries": 10})
    search = dispatch_tool(registry, "search_files", {"query": "hello"})

    assert tree["ok"] is True
    assert {"path": "app.py", "type": "file"} in tree["entries"]
    assert search["ok"] is True
    assert search["matches"][0]["path"] == "app.py"
