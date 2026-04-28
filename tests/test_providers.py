import pytest

from tiny_code_agent.providers import build_llm_client, default_model_for_provider


def test_default_model_for_openai() -> None:
    assert default_model_for_provider("openai") == "gpt-5.5"


def test_unknown_provider_has_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported provider"):
        default_model_for_provider("deepseek")


def test_build_unknown_provider_has_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported provider"):
        build_llm_client("anthropic")
