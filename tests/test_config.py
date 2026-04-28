from pathlib import Path

from tiny_code_agent.config import load_dotenv


def test_load_dotenv_sets_missing_values(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY='test-key'\n# comment\nEMPTY=\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_dotenv(env_file)

    assert "OPENAI_API_KEY" in __import__("os").environ
    assert __import__("os").environ["OPENAI_API_KEY"] == "test-key"


def test_load_dotenv_does_not_override_existing_values(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "shell-key")

    load_dotenv(env_file)

    assert __import__("os").environ["OPENAI_API_KEY"] == "shell-key"
