from tiny_code_agent.cli import build_parser, main


def test_parser_has_workspace_and_model_options() -> None:
    parser = build_parser()
    args = parser.parse_args(["--workspace", ".", "--provider", "openai", "--model", "test-model"])

    assert args.workspace == "."
    assert args.provider == "openai"
    assert args.model == "test-model"


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
