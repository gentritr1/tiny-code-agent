import pytest

from tiny_code_agent.providers import factory
from tiny_code_agent.llm import LLMProviderError
from tiny_code_agent.providers import (
    all_supported_models,
    build_llm_client,
    default_model_for_provider,
    supported_models_for_provider,
    supported_providers,
)
from tiny_code_agent.providers.openai import _normalize_openai_error


def test_default_model_for_openai() -> None:
    assert default_model_for_provider("openai") == "gpt-5.5"


def test_supported_provider_helpers() -> None:
    assert supported_providers() == ["openai"]
    assert supported_models_for_provider("openai") == ["gpt-5.5"]
    assert all_supported_models() == ["gpt-5.5"]


def test_supported_provider_helpers_scale_to_multiple_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        factory,
        "PROVIDER_MODELS",
        {
            "openai": ["gpt-5.5", "gpt-5.5-mini"],
            "anthropic": ["claude-3-7-sonnet", "claude-3-5-haiku"],
        },
    )

    assert supported_providers() == ["anthropic", "openai"]
    assert supported_models_for_provider("openai") == ["gpt-5.5", "gpt-5.5-mini"]
    assert default_model_for_provider("anthropic") == "claude-3-7-sonnet"
    assert all_supported_models() == [
        "claude-3-5-haiku",
        "claude-3-7-sonnet",
        "gpt-5.5",
        "gpt-5.5-mini",
    ]


def test_unknown_provider_has_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported provider"):
        default_model_for_provider("deepseek")


def test_build_unknown_provider_has_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported provider"):
        build_llm_client("anthropic")


def test_normalize_openai_error_falls_back_to_generic_message() -> None:
    error = _normalize_openai_error(RuntimeError("boom"))

    assert isinstance(error, LLMProviderError)
    assert error.message == "OpenAI request failed: boom"
