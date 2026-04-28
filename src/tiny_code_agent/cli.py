from __future__ import annotations

import argparse
import os
from pathlib import Path

from .agent import CodingAgent
from .config import load_dotenv
from .providers import build_llm_client, default_model_for_provider
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
        help="LLM provider to use. Defaults to TINY_CODE_AGENT_PROVIDER or openai.",
    )
    parser.add_argument(
        "--model",
        default=default_model,
        help="LLM model name. Defaults to TINY_CODE_AGENT_MODEL or the provider default.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(".env"))

    parser = build_parser()
    args = parser.parse_args(argv)

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

        answer = agent.ask(user_input)
        print(f"Assistant: {answer}")
