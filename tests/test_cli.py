from io import StringIO

from tiny_code_agent.cli import build_parser, main


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
