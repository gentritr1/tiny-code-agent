from io import StringIO
from pathlib import Path
import runpy

from tiny_code_agent.llm import LLMProviderError
from tiny_code_agent.cli import (
    TerminalUI,
    _normalize_user_input,
    _parse_tool_trace,
    _summarize_text,
    _thinking_phrase,
    build_parser,
    main,
)


def test_parser_has_workspace_and_model_options() -> None:
    parser = build_parser()
    args = parser.parse_args(["--workspace", ".", "--provider", "openai", "--model", "test-model"])

    assert args.workspace == "."
    assert args.provider == "openai"
    assert args.model == "test-model"


def test_parser_accepts_list_models_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["--list-models"])

    assert args.list_models is True


def test_parser_accepts_provider_listing_and_completion_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(["--list-providers", "--generate-completion", "bash", "--plain"])

    assert args.list_providers is True
    assert args.generate_completion == "bash"
    assert args.plain is True


def test_list_models_prints_supported_models(monkeypatch) -> None:
    stdout = StringIO()
    monkeypatch.setattr("sys.stdout", stdout)

    assert main(["--list-models"]) == 0
    assert "Supported providers and known models:" in stdout.getvalue()
    assert "- openai: gpt-5-mini (default), gpt-5-nano" in stdout.getvalue()


def test_list_providers_prints_supported_providers(monkeypatch) -> None:
    stdout = StringIO()
    monkeypatch.setattr("sys.stdout", stdout)

    assert main(["--list-providers"]) == 0
    assert "Supported providers:" in stdout.getvalue()
    assert "- openai" in stdout.getvalue()


def test_generate_completion_prints_bash_script(monkeypatch) -> None:
    stdout = StringIO()
    monkeypatch.setattr("sys.stdout", stdout)

    assert main(["--generate-completion", "bash"]) == 0
    assert "_tiny_code_agent_completions()" in stdout.getvalue()
    assert "--list-providers" in stdout.getvalue()
    assert "--plain" in stdout.getvalue()
    assert "gpt-5-mini" in stdout.getvalue()
    assert "gpt-5-nano" in stdout.getvalue()


def test_generate_completion_prints_zsh_script(monkeypatch) -> None:
    stdout = StringIO()
    monkeypatch.setattr("sys.stdout", stdout)

    assert main(["--generate-completion", "zsh"]) == 0
    assert "#compdef tiny-code-agent" in stdout.getvalue()
    assert "compdef _tiny_code_agent tiny-code-agent" in stdout.getvalue()
    assert "gpt-5-mini" in stdout.getvalue()


def test_list_models_renders_multiple_providers_and_defaults(monkeypatch) -> None:
    stdout = StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr(
        "tiny_code_agent.cli.supported_providers",
        lambda: ["anthropic", "openai"],
    )
    monkeypatch.setattr(
        "tiny_code_agent.cli.supported_models_for_provider",
        lambda provider: {
            "anthropic": ["claude-3-7-sonnet", "claude-3-5-haiku"],
            "openai": ["gpt-5-mini", "gpt-5-nano"],
        }[provider],
    )
    monkeypatch.setattr(
        "tiny_code_agent.cli.default_model_for_provider",
        lambda provider: {
            "anthropic": "claude-3-7-sonnet",
            "openai": "gpt-5-mini",
        }[provider],
    )

    assert main(["--list-models"]) == 0
    output = stdout.getvalue()
    assert "- anthropic: claude-3-7-sonnet (default), claude-3-5-haiku" in output
    assert "- openai: gpt-5-mini (default), gpt-5-nano" in output


def test_missing_api_key_exits_with_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("tiny_code_agent.cli.load_dotenv", lambda path: None)

    try:
        main([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")


def test_cli_starts_and_exits_cleanly(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("builtins.input", lambda: "exit")

    assert main([]) == 0


def test_cli_reports_provider_errors_without_traceback(monkeypatch) -> None:
    class FailingClient:
        provider_name = "fake"

        def complete(self, **kwargs):
            raise LLMProviderError("quota exceeded")

        def tool_result_message(self, result):
            raise AssertionError("tool_result_message should not be called")

    stdout = StringIO()
    stderr = StringIO()
    inputs = iter(["create hello.py", "exit"])

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("tiny_code_agent.cli.build_llm_client", lambda provider: FailingClient())
    monkeypatch.setattr("builtins.input", lambda: next(inputs))
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)

    assert main([]) == 0
    assert "Traceback" not in stderr.getvalue()
    assert "Error: quota exceeded" in stderr.getvalue()


def test_terminal_ui_plain_rendering_without_tty() -> None:
    stdout = StringIO()
    stderr = StringIO()
    ui = TerminalUI(stdout=stdout, stderr=stderr)

    ui.start_thinking("read the readme")
    ui.banner(provider="openai", model="gpt-5-mini", workspace=__import__("pathlib").Path("/tmp/demo"))
    ui.tool('tool: read_file {"path": "README.md"}')
    ui.assistant("Done.")
    ui.error("quota exceeded")

    output = stdout.getvalue()
    assert "Tiny Code Agent v0.1" in output
    assert "Provider: openai" in output
    assert "Tool: read_file" in output
    assert "  path: README.md" in output
    assert "Assistant: Done." in output
    assert "\033[" not in output
    assert "Error: quota exceeded" in stderr.getvalue()


def test_terminal_ui_summarizes_multiline_tool_text() -> None:
    stdout = StringIO()
    stderr = StringIO()
    ui = TerminalUI(stdout=stdout, stderr=stderr)

    ui.tool('tool: edit_file {"path": "a.txt", "new_str": "line 1\\nline 2"}')

    output = stdout.getvalue()
    assert "Tool: edit_file" in output
    assert "  path: a.txt" in output
    assert "  new_str: line 1\\nline 2" in output


def test_terminal_ui_renders_tool_result_status() -> None:
    stdout = StringIO()
    stderr = StringIO()
    ui = TerminalUI(stdout=stdout, stderr=stderr)

    ui.tool('tool_result: edit_file {"ok": true, "path": "/tmp/a.txt"}')
    ui.tool('tool_result: read_file {"ok": false, "error": "file_not_found"}')

    output = stdout.getvalue()
    assert "result: ok" in output
    assert "path: /tmp/a.txt" in output
    assert "result: error: file_not_found" in output


def test_terminal_ui_write_prompt_renders_once() -> None:
    stdout = StringIO()
    stderr = StringIO()
    ui = TerminalUI(stdout=stdout, stderr=stderr)

    ui.write_prompt()

    assert stdout.getvalue() == "You: "


class FakeTTY(StringIO):
    def isatty(self) -> bool:
        return True


def test_terminal_ui_uses_color_and_animation_on_tty(monkeypatch) -> None:
    stdout = FakeTTY()
    stderr = FakeTTY()
    sleeps: list[float] = []

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("tiny_code_agent.cli.time.sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr("tiny_code_agent.cli.random.choice", lambda options: options[0])

    ui = TerminalUI(stdout=stdout, stderr=stderr)
    ui.start_thinking("create a file")
    ui.banner(provider="openai", model="gpt-5-mini", workspace=Path("/tmp/demo"))
    ui.tool('tool: read_file {"path": "README.md"}')
    ui.assistant("Done.")
    ui.error("quota exceeded")

    output = stdout.getvalue()
    assert "\033[" in output
    assert "Sketching the edit..." in output
    assert "Starting" in output
    assert "Tiny Code Agent v0.1" in output
    assert 'Tool' in output
    assert len(sleeps) == 3
    assert "\033[" in stderr.getvalue()


def test_terminal_ui_disables_color_with_no_color(monkeypatch) -> None:
    stdout = FakeTTY()
    stderr = FakeTTY()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("NO_COLOR", "1")

    ui = TerminalUI(stdout=stdout, stderr=stderr)
    ui.banner(provider="openai", model="gpt-5-mini", workspace=Path("/tmp/demo"))

    assert "\033[" not in stdout.getvalue()


def test_terminal_ui_plain_flag_disables_tty_color_and_thinking(monkeypatch, tmp_path) -> None:
    stdout = FakeTTY()
    stderr = FakeTTY()

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)

    ui = TerminalUI(stdout=stdout, stderr=stderr, plain=True)
    ui.start_thinking("create a file")
    ui.banner(provider="openai", model="gpt-5-mini", workspace=tmp_path)

    assert "\033[" not in stdout.getvalue()
    assert "Sketching" not in stdout.getvalue()


def test_cli_reports_invalid_provider_from_factory(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("tiny_code_agent.cli.build_llm_client", lambda provider: (_ for _ in ()).throw(ValueError("unsupported provider 'bad'")))

    try:
        main(["--provider", "openai"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")


def test_cli_returns_cleanly_on_eof(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("builtins.input", lambda: (_ for _ in ()).throw(EOFError()))

    assert main([]) == 0


def test_cli_skips_empty_input_and_prints_assistant_reply(monkeypatch) -> None:
    class FakeClient:
        provider_name = "fake"

        def complete(self, **kwargs):
            return __import__("tiny_code_agent.llm").llm.AssistantTurn(
                response_id="resp_fake",
                messages=[{"role": "assistant", "content": "Hi"}],
                text="Hi",
                tool_calls=[],
            )

        def tool_result_message(self, result):
            raise AssertionError("tool_result_message should not be called")

    stdout = StringIO()
    inputs = iter(["", "hello", "exit"])

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("tiny_code_agent.cli.build_llm_client", lambda provider: FakeClient())
    monkeypatch.setattr("builtins.input", lambda: next(inputs))
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("tiny_code_agent.cli.random.choice", lambda options: options[0])

    assert main([]) == 0
    assert "Sketching" not in stdout.getvalue()
    assert "Assistant: Hi" in stdout.getvalue()


def test_cli_shows_thinking_indicator_on_tty(monkeypatch) -> None:
    class FakeClient:
        provider_name = "fake"

        def complete(self, **kwargs):
            return __import__("tiny_code_agent.llm").llm.AssistantTurn(
                response_id="resp_fake",
                messages=[{"role": "assistant", "content": "Hi"}],
                text="Hi",
                tool_calls=[],
            )

        def tool_result_message(self, result):
            raise AssertionError("tool_result_message should not be called")

    stdout = FakeTTY()
    stderr = FakeTTY()
    inputs = iter(["hello", "exit"])

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("tiny_code_agent.cli.build_llm_client", lambda provider: FakeClient())
    monkeypatch.setattr("builtins.input", lambda: next(inputs))
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    monkeypatch.setattr("tiny_code_agent.cli.time.sleep", lambda seconds: None)
    monkeypatch.setattr("tiny_code_agent.cli.random.choice", lambda options: options[0])

    assert main([]) == 0
    assert "Thinking..." in stdout.getvalue()
    assert "Assistant" in stdout.getvalue()


def test_cli_supports_session_commands(monkeypatch) -> None:
    stdout = StringIO()
    inputs = iter(["/help", "/models", "/workspace", "/exit"])

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("tiny_code_agent.cli.supported_providers", lambda: ["openai"])
    monkeypatch.setattr(
        "tiny_code_agent.cli.supported_models_for_provider",
        lambda provider: ["gpt-5-mini", "gpt-5-nano"] if provider == "openai" else [],
    )
    monkeypatch.setattr(
        "tiny_code_agent.cli.default_model_for_provider",
        lambda provider: "gpt-5-mini" if provider == "openai" else "gpt-5-mini",
    )
    monkeypatch.setattr("builtins.input", lambda: next(inputs))
    monkeypatch.setattr("sys.stdout", stdout)

    assert main([]) == 0
    output = stdout.getvalue()
    assert "Commands: /help, /models, /workspace, /exit, /quit" in output
    assert "openai: gpt-5-mini (default), gpt-5-nano" in output
    assert "Workspace:" in output


def test_cli_reports_unknown_session_command(monkeypatch) -> None:
    stdout = StringIO()
    stderr = StringIO()
    inputs = iter(["/wat", "exit"])

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("builtins.input", lambda: next(inputs))
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)

    assert main([]) == 0
    assert "Unknown command: /wat" in stderr.getvalue()


def test_cli_normalizes_accidental_prompt_prefix(monkeypatch) -> None:
    class FakeClient:
        provider_name = "fake"
        seen_messages = []

        def complete(self, **kwargs):
            self.seen_messages.append(kwargs["messages"])
            return __import__("tiny_code_agent.llm").llm.AssistantTurn(
                response_id="resp_fake",
                messages=[{"role": "assistant", "content": "Bye"}],
                text="Bye",
                tool_calls=[],
            )

        def tool_result_message(self, result):
            raise AssertionError("tool_result_message should not be called")

    stdout = StringIO()
    inputs = iter(["You: hello", "exit"])
    client = FakeClient()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("tiny_code_agent.cli.build_llm_client", lambda provider: client)
    monkeypatch.setattr("builtins.input", lambda: next(inputs))
    monkeypatch.setattr("sys.stdout", stdout)

    assert main([]) == 0
    assert client.seen_messages[0] == [{"role": "user", "content": "hello"}]


def test_normalize_user_input_strips_prompt_prefix() -> None:
    assert _normalize_user_input("You: exit") == "exit"
    assert _normalize_user_input("  you: hello  ") == "hello"
    assert _normalize_user_input("plain text") == "plain text"


def test_thinking_phrase_varies_by_request(monkeypatch) -> None:
    monkeypatch.setattr("tiny_code_agent.cli.random.choice", lambda options: options[-1])

    assert _thinking_phrase("create a file") == "Shaping the patch..."
    assert _thinking_phrase("read the readme") == "Pulling the thread..."
    assert _thinking_phrase("find the tests") == "Following the breadcrumbs..."
    assert _thinking_phrase("hello there") == "Piecing it together..."


def test_tool_trace_helpers_format_common_cases() -> None:
    name, arguments = _parse_tool_trace(
        'tool: edit_file {"path": "hello.py", "old_str": "", "new_str": "hello"}'
    )

    assert name == "edit_file"
    assert arguments == {"path": "hello.py", "old_str": "", "new_str": "hello"}
    assert _parse_tool_trace("tool: list_files")[1] == {}
    assert _parse_tool_trace("tool: read_file {bad")[1] == {"arguments": "{bad"}
    assert _parse_tool_trace('tool: demo ["x"]')[1] == {"arguments": ["x"]}
    assert _summarize_text("short") == "short"
    assert _summarize_text("a" * 90) == ("a" * 77) + "..."


def test_module_entrypoint_calls_main(monkeypatch) -> None:
    monkeypatch.setattr("tiny_code_agent.cli.main", lambda: 7)

    try:
        runpy.run_module("tiny_code_agent.__main__", run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 7
    else:
        raise AssertionError("expected SystemExit")
