from __future__ import annotations

from .openai import OpenAIClient


DEFAULT_PROVIDER = "openai"
DEFAULT_MODELS = {
    "openai": "gpt-5.5",
}


def default_model_for_provider(provider: str) -> str:
    try:
        return DEFAULT_MODELS[provider]
    except KeyError as exc:
        supported = ", ".join(sorted(DEFAULT_MODELS))
        raise ValueError(f"unsupported provider '{provider}'. Supported providers: {supported}") from exc


def build_llm_client(provider: str):
    if provider == "openai":
        return OpenAIClient()

    supported = ", ".join(sorted(DEFAULT_MODELS))
    raise ValueError(f"unsupported provider '{provider}'. Supported providers: {supported}")
