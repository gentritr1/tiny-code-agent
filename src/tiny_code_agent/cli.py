from __future__ import annotations

import argparse
import os
from pathlib import Path

from .agent import CodingAgent, OpenAIResponseClient
from .config import load_dotenv
from .tools import build_tool_registry


DEFAULT_MODEL = "gpt-5.5"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiny-code-agent",
        description="Run a small OpenAI-powered coding agent in the current workspace.",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root the agent may read and edit. Defaults to the current directory.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("TINY_CODE_AGENT_MODEL", DEFAULT_MODEL),
        help="OpenAI model name. Defaults to TINY_CODE_AGENT_MODEL or gpt-5.5.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(".env"))

    parser = build_parser()
    args = parser.parse_args(argv)

    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required. Set it in your shell or .env loader.")

    workspace = Path(args.workspace).expanduser().resolve()
    registry = build_tool_registry(workspace)
    agent = CodingAgent(
        client=OpenAIResponseClient(),
        model=args.model,
        registry=registry,
        printer=lambda message: print(message),
    )

    print(f"Tiny Code Agent v0.1")
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
