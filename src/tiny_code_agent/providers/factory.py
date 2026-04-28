from __future__ import annotations

from .openai import OpenAIClient


DEFAULT_PROVIDER = "openai"
PROVIDER_MODELS = {
    "openai": ["gpt-5.5"],
}
CLIENT_BUILDERS = {
    "openai": OpenAIClient,
}


def supported_providers() -> list[str]:
    return sorted(PROVIDER_MODELS)


def supported_models_for_provider(provider: str) -> list[str]:
    try:
        return list(PROVIDER_MODELS[provider])
    except KeyError as exc:
        supported = ", ".join(supported_providers())
        raise ValueError(f"unsupported provider '{provider}'. Supported providers: {supported}") from exc


def all_supported_models() -> list[str]:
    models = {model for provider in supported_providers() for model in supported_models_for_provider(provider)}
    return sorted(models)


def default_model_for_provider(provider: str) -> str:
    try:
        return PROVIDER_MODELS[provider][0]
    except KeyError as exc:
        supported = ", ".join(supported_providers())
        raise ValueError(f"unsupported provider '{provider}'. Supported providers: {supported}") from exc


def build_llm_client(provider: str):
    try:
        builder = CLIENT_BUILDERS[provider]
    except KeyError as exc:
        supported = ", ".join(supported_providers())
        raise ValueError(f"unsupported provider '{provider}'. Supported providers: {supported}") from exc
    return builder()
