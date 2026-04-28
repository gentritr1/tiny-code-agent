from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from typing import Any
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


class TerminalUI:
    def __init__(self, *, stdout, stderr, plain: bool = False) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.plain = plain
        self.use_color = _supports_color(stdout) and not os.environ.get("NO_COLOR") and not plain
        self.use_animation = self.use_color and _is_tty(stdout)
        self.thinking_active = False
        self.separate_next_prompt = False

    def banner(self, *, provider: str, model: str, workspace: Path) -> None:
        self._animate_startup()
        self.line(self._accent("Tiny Code Agent v0.1"))
        self.line(f"{self._label('Provider')} {provider}")
        self.line(f"{self._label('Model')} {model}")
        self.line(f"{self._label('Workspace')} {workspace}")
        self.line(f"{self._muted('Type exit or quit to stop.')}")
        self.separate_next_prompt = True

    def prompt(self) -> str:
        return f"{self._user('You')} "

    def write_prompt(self) -> None:
        print(self.prompt(), end="", file=self.stdout, flush=True)

    def tool(self, message: str) -> None:
        self.stop_thinking()
        if message.startswith("tool_result:"):
            self.tool_result(message)
            return
        name, arguments = _parse_tool_trace(message)
        self.line(f"{self._tool('Tool')} {name}")
        for key, value in arguments.items():
            if key == "new_str" and isinstance(value, str):
                value = _summarize_text(value)
            self.line(f"  {key}: {value}")
        self.separate_next_prompt = False

    def tool_result(self, message: str) -> None:
        name, result = _parse_tool_trace(message.removeprefix("tool_result:").strip())
        status = "ok" if result.get("ok") else f"error: {result.get('error', 'unknown')}"
        self.line(f"  result: {status}")
        path = result.get("path")
        if path:
            self.line(f"  path: {path}")
        self.separate_next_prompt = False

    def assistant(self, message: str) -> None:
        self.stop_thinking()
        self.line(f"{self._assistant('Assistant')} {message}")
        self.separate_next_prompt = True

    def error(self, message: str) -> None:
        self.stop_thinking()
        self.line(f"{self._error('Error')} {message}", stream=self.stderr)
        self.separate_next_prompt = True

    def start_thinking(self, user_input: str) -> None:
        if self.thinking_active or self.plain or not _is_tty(self.stdout):
            return
        self.thinking_active = True
        self.line(self._muted(_thinking_phrase(user_input)))

    def stop_thinking(self) -> None:
        self.thinking_active = False

    def before_prompt(self) -> None:
        self.stop_thinking()
        if self.separate_next_prompt:
            self.line()
            self.separate_next_prompt = False

    def line(self, text: str = "", *, stream=None) -> None:
        print(text, file=stream or self.stdout, flush=True)

    def _animate_startup(self) -> None:
        if not self.use_animation:
            return
        frames = ["·  ", "·· ", "···"]
        for frame in frames:
            print(f"\r{self._muted('Starting')} {self._accent(frame)}", end="", file=self.stdout, flush=True)
            time.sleep(0.06)
        print("\r" + " " * 24 + "\r", end="", file=self.stdout, flush=True)

    def _style(self, code: str, text: str) -> str:
        if not self.use_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def _accent(self, text: str) -> str:
        return self._style("1;36", text)

    def _label(self, text: str) -> str:
        return self._style("1;34", f"{text}:")

    def _muted(self, text: str) -> str:
        return self._style("2", text)

    def _user(self, text: str) -> str:
        return self._style("1;33", f"{text}:")

    def _tool(self, text: str) -> str:
        return self._style("1;35", f"{text}:")

    def _assistant(self, text: str) -> str:
        return self._style("1;32", f"{text}:")

    def _error(self, text: str) -> str:
        return self._style("1;31", f"{text}:")


def _is_tty(stream) -> bool:
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _supports_color(stream) -> bool:
    return _is_tty(stream) and os.environ.get("TERM") not in {None, "dumb"}


def _normalize_user_input(text: str) -> str:
    trimmed = text.strip()
    if trimmed.lower().startswith("you:"):
        return trimmed[4:].strip()
    return trimmed


def _thinking_phrase(user_input: str) -> str:
    prompt = user_input.lower()
    if any(word in prompt for word in ["create", "write", "edit", "update", "change"]):
        options = [
            "Sketching the edit...",
            "Lining up the file change...",
            "Shaping the patch...",
        ]
    elif any(word in prompt for word in ["read", "explain", "summarize", "describe"]):
        options = [
            "Reading through it...",
            "Tracing the relevant bits...",
            "Pulling the thread...",
        ]
    elif any(word in prompt for word in ["list", "find", "search", "show", "where"]):
        options = [
            "Scanning the workspace...",
            "Looking around...",
            "Following the breadcrumbs...",
        ]
    else:
        options = [
            "Thinking...",
            "Plotting the next move...",
            "Piecing it together...",
        ]
    return random.choice(options)


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
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Disable colors, animation, and thinking phrases for plain terminal output.",
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

    COMPREPLY=( $(compgen -W "--workspace --provider --model --list-models --list-providers --generate-completion --plain" -- "$cur") )
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
    '--generate-completion[Print a shell completion script]:shell:(bash zsh)' \\
    '--plain[Disable colors, animation, and thinking phrases]'
}}

compdef _tiny_code_agent tiny-code-agent
"""


def _parse_tool_trace(message: str) -> tuple[str, dict[str, Any]]:
    trace = message.removeprefix("tool: ").strip()
    name, _, raw_arguments = trace.partition(" ")
    if not raw_arguments:
        return name, {}
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return name, {"arguments": raw_arguments}
    if isinstance(arguments, dict):
        return name, arguments
    return name, {"arguments": arguments}


def _summarize_text(text: str, limit: int = 80) -> str:
    normalized = text.replace("\n", "\\n")
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _handle_command(command: str, *, ui: TerminalUI, provider: str, model: str, workspace: Path) -> bool:
    normalized = command.strip().lower()
    if normalized in {"/exit", "/quit"}:
        raise SystemExit(0)
    if normalized == "/help":
        ui.line("Commands: /help, /models, /workspace, /exit, /quit")
        return True
    if normalized == "/models":
        for provider_name in supported_providers():
            ui.line(f"{provider_name}: {_format_models(provider_name)}")
        return True
    if normalized == "/workspace":
        ui.line(f"Provider: {provider}")
        ui.line(f"Model: {model}")
        ui.line(f"Workspace: {workspace}")
        return True
    ui.error(f"Unknown command: {command}")
    return True


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(".env"))

    parser = build_parser()
    args = parser.parse_args(argv)
    ui = TerminalUI(stdout=sys.stdout, stderr=sys.stderr, plain=args.plain)

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
        printer=ui.tool,
    )

    ui.banner(provider=args.provider, model=args.model, workspace=workspace)

    while True:
        try:
            ui.before_prompt()
            ui.write_prompt()
            user_input = input()
        except (EOFError, KeyboardInterrupt):
            ui.line()
            return 0

        user_input = _normalize_user_input(user_input)
        if user_input.lower() in {"exit", "quit"}:
            return 0
        if user_input.startswith("/"):
            try:
                if _handle_command(
                    user_input,
                    ui=ui,
                    provider=args.provider,
                    model=args.model,
                    workspace=workspace,
                ):
                    continue
            except SystemExit as exc:
                return int(exc.code)
        if not user_input:
            continue

        try:
            ui.start_thinking(user_input)
            answer = agent.ask(user_input)
        except LLMProviderError as exc:
            ui.error(exc.message)
            continue

        ui.assistant(answer)
