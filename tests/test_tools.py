from pathlib import Path
import os

from tiny_code_agent.tools import dispatch_tool, edit_file, list_files, read_file, resolve_workspace_path
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
    monkeypatch.setattr(Path, "read_text", lambda self, encoding="utf-8": (_ for _ in ()).throw(OSError("boom")))

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
    monkeypatch.setattr(Path, "write_text", lambda self, text, encoding="utf-8": (_ for _ in ()).throw(OSError("boom")))

    result = edit_file(tmp_path, "main.py", "hello", "bye")

    assert result["ok"] is False
    assert result["error"] == "os_error"


def test_tool_schema_includes_strict_flag() -> None:
    tool = Tool(
        name="demo",
        description="desc",
        parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
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
