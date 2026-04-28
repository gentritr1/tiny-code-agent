from io import StringIO

from tiny_code_agent.llm import LLMProviderError
from tiny_code_agent.cli import TerminalUI, build_parser, main


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
    args = parser.parse_args(["--list-providers", "--generate-completion", "bash"])

    assert args.list_providers is True
    assert args.generate_completion == "bash"


def test_list_models_prints_supported_models(monkeypatch) -> None:
    stdout = StringIO()
    monkeypatch.setattr("sys.stdout", stdout)

    assert main(["--list-models"]) == 0
    assert "Supported providers and known models:" in stdout.getvalue()
    assert "- openai: gpt-5.5 (default)" in stdout.getvalue()


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
    assert "gpt-5.5" in stdout.getvalue()


def test_generate_completion_prints_zsh_script(monkeypatch) -> None:
    stdout = StringIO()
    monkeypatch.setattr("sys.stdout", stdout)

    assert main(["--generate-completion", "zsh"]) == 0
    assert "#compdef tiny-code-agent" in stdout.getvalue()
    assert "compdef _tiny_code_agent tiny-code-agent" in stdout.getvalue()
    assert "gpt-5.5" in stdout.getvalue()


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
            "openai": ["gpt-5.5", "gpt-5.5-mini"],
        }[provider],
    )
    monkeypatch.setattr(
        "tiny_code_agent.cli.default_model_for_provider",
        lambda provider: {
            "anthropic": "claude-3-7-sonnet",
            "openai": "gpt-5.5",
        }[provider],
    )

    assert main(["--list-models"]) == 0
    output = stdout.getvalue()
    assert "- anthropic: claude-3-7-sonnet (default), claude-3-5-haiku" in output
    assert "- openai: gpt-5.5 (default), gpt-5.5-mini" in output


def test_missing_api_key_exits_with_clear_error(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    try:
        main([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")


def test_cli_starts_and_exits_cleanly(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("builtins.input", lambda prompt: "exit")

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
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)

    assert main([]) == 0
    assert "Traceback" not in stderr.getvalue()
    assert "Error: quota exceeded" in stderr.getvalue()


def test_terminal_ui_plain_rendering_without_tty() -> None:
    stdout = StringIO()
    stderr = StringIO()
    ui = TerminalUI(stdout=stdout, stderr=stderr)

    ui.banner(provider="openai", model="gpt-5.5", workspace=__import__("pathlib").Path("/tmp/demo"))
    ui.tool('tool: read_file {"path": "README.md"}')
    ui.assistant("Done.")
    ui.error("quota exceeded")

    output = stdout.getvalue()
    assert "Tiny Code Agent v0.1" in output
    assert "Provider: openai" in output
    assert 'Tool: read_file {"path": "README.md"}' in output
    assert "Assistant: Done." in output
    assert "\033[" not in output
    assert "Error: quota exceeded" in stderr.getvalue()
