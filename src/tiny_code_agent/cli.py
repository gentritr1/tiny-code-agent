from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .agent import CodingAgent
from .config import load_dotenv
from .llm import LLMProviderError
from .providers import (
    all_supported_models,
    build_llm_client,
    default_model_for_provider,
    supported_models_for_provider,
    supported_providers,
)
from .providers.factory import DEFAULT_PROVIDER
from .tools import build_tool_registry


def build_parser() -> argparse.ArgumentParser:
    provider = os.environ.get("TINY_CODE_AGENT_PROVIDER", DEFAULT_PROVIDER)
    default_model = os.environ.get("TINY_CODE_AGENT_MODEL", default_model_for_provider(provider))
    parser = argparse.ArgumentParser(
        prog="tiny-code-agent",
        description="Run a small provider-agnostic coding agent in the current workspace.",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root the agent may read and edit. Defaults to the current directory.",
    )
    parser.add_argument(
        "--provider",
        default=provider,
        choices=supported_providers(),
        help="LLM provider to use. Defaults to TINY_CODE_AGENT_PROVIDER or openai.",
    )
    parser.add_argument(
        "--model",
        default=default_model,
        help="LLM model name. Defaults to TINY_CODE_AGENT_MODEL or the provider default.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Print the providers and known models supported by this CLI, then exit.",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="Print the supported providers, then exit.",
    )
    parser.add_argument(
        "--generate-completion",
        choices=["bash", "zsh"],
        help="Print a shell completion script for tiny-code-agent, then exit.",
    )
    return parser


def _format_models(provider: str) -> str:
    default_model = default_model_for_provider(provider)
    models = []
    for model in supported_models_for_provider(provider):
        suffix = " (default)" if model == default_model else ""
        models.append(f"{model}{suffix}")
    return ", ".join(models)


def _print_supported_providers() -> None:
    print("Supported providers:")
    for provider in supported_providers():
        print(f"- {provider}")


def _print_supported_models() -> None:
    print("Supported providers and known models:")
    for provider in supported_providers():
        print(f"- {provider}: {_format_models(provider)}")


def _completion_script(shell: str) -> str:
    providers = " ".join(supported_providers())
    models = " ".join(all_supported_models())

    if shell == "bash":
        return f"""_tiny_code_agent_completions()
{{
    local cur prev
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    case "$prev" in
        --provider)
            COMPREPLY=( $(compgen -W "{providers}" -- "$cur") )
            return
            ;;
        --model)
            COMPREPLY=( $(compgen -W "{models}" -- "$cur") )
            return
            ;;
        --generate-completion)
            COMPREPLY=( $(compgen -W "bash zsh" -- "$cur") )
            return
            ;;
    esac

    COMPREPLY=( $(compgen -W "--workspace --provider --model --list-models --list-providers --generate-completion" -- "$cur") )
}}

complete -F _tiny_code_agent_completions tiny-code-agent
"""

    return f"""#compdef tiny-code-agent

_tiny_code_agent() {{
  local -a providers models
  providers=({providers})
  models=({models})

  _arguments \\
    '--workspace[Workspace root the agent may read and edit]:workspace:_files' \\
    '--provider[LLM provider to use]:provider:({providers})' \\
    '--model[LLM model name]:model:({models})' \\
    '--list-models[Print the providers and known models supported by this CLI]' \\
    '--list-providers[Print the supported providers]' \\
    '--generate-completion[Print a shell completion script]:shell:(bash zsh)'
}}

compdef _tiny_code_agent tiny-code-agent
"""


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(".env"))

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_providers:
        _print_supported_providers()
        return 0

    if args.list_models:
        _print_supported_models()
        return 0

    if args.generate_completion:
        print(_completion_script(args.generate_completion), end="")
        return 0

    if args.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required for provider=openai.")

    workspace = Path(args.workspace).expanduser().resolve()
    registry = build_tool_registry(workspace)
    try:
        client = build_llm_client(args.provider)
    except ValueError as exc:
        parser.error(str(exc))

    agent = CodingAgent(
        client=client,
        model=args.model,
        registry=registry,
        printer=lambda message: print(message),
    )

    print(f"Tiny Code Agent v0.1")
    print(f"Provider: {args.provider}")
    print(f"Model: {args.model}")
    print(f"Workspace: {workspace}")
    print("Type exit or quit to stop.")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if user_input.lower() in {"exit", "quit"}:
            return 0
        if not user_input:
            continue

        try:
            answer = agent.ask(user_input)
        except LLMProviderError as exc:
            print(f"Error: {exc.message}", file=sys.stderr)
            continue

        print(f"Assistant: {answer}")
