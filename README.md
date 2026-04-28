# Tiny Code Agent

Tiny Code Agent is a small Python CLI coding agent inspired by Mihail Eric's
"How to Code Claude Code in 200 Lines of Code" article. It teaches the core
agent loop without hiding the moving parts:

1. send the user message to an LLM
2. let the model request a tool call
3. run that tool locally
4. send the tool result back
5. repeat until the model gives a final answer

The `v0.1` version supports three safe workspace-limited file tools:

- `list_files`
- `read_file`
- `edit_file`

It also includes:

- provider and model discovery with `--list-providers` and `--list-models`
- generated bash and zsh completion scripts
- clearer provider/API error messages instead of raw Python tracebacks
- lightweight terminal UX for interactive sessions, including colors and a small startup animation

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Add your API key to `.env` or export it in your shell:

```bash
export OPENAI_API_KEY="sk-your-api-key"
```

Optional provider/model override:

```bash
export TINY_CODE_AGENT_PROVIDER="openai"
export TINY_CODE_AGENT_MODEL="gpt-5-mini"
```

For cheaper testing, the curated default is `gpt-5-mini`. The bundled model
list also includes `gpt-5-nano` as an even cheaper option.

To inspect the providers and models supported by this CLI:

```bash
tiny-code-agent --list-providers
tiny-code-agent --list-models
```

To generate shell completions:

```bash
tiny-code-agent --generate-completion bash
tiny-code-agent --generate-completion zsh
```

Example for the current shell session:

```bash
eval "$(tiny-code-agent --generate-completion bash)"
```

When you add more models later, update the provider registry in
`src/tiny_code_agent/providers/factory.py` and these commands will pick them up.

The core agent is provider-agnostic. OpenAI is the first implemented provider,
and the provider adapter layer is designed so Anthropic, DeepSeek, or another
tool-calling LLM can be added without changing the local file tools.

## Run

```bash
python -m tiny_code_agent
```

or, after installation:

```bash
tiny-code-agent
```

Type `exit` or `quit` to end the session. In an interactive terminal, the CLI
uses simple colors to distinguish user, tool, assistant, and error output.
It also shows a lightweight thinking line with request-aware phrases while
waiting on the model. Set `NO_COLOR=1` or pass `--plain` to disable ANSI colors
and animation.

If you accidentally type input like `You: exit`, the CLI strips the leading
`You:` prompt text automatically.

Session commands:

- `/help`
- `/models`
- `/workspace`
- `/exit`

## Example

```text
You: Create hello.py with a hello function.
tool: edit_file {"path": "hello.py", "old_str": "", "new_str": "..."}
Assistant: Created hello.py with a hello function.
```

The exact tool trace depends on the model, but the loop is always the same:
the model asks for tools, the CLI runs them, and the model receives structured
results.

## Manual Smoke Test

The live agent run requires a real `OPENAI_API_KEY`. Without that, only the
unit tests and the listing/completion commands will work.

From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
export OPENAI_API_KEY="sk-your-api-key"
python -m tiny_code_agent --list-models
python -m tiny_code_agent
```

At the `You:` prompt, try:

```text
Create hello.py with a hello function.
```

Expected behavior:

- the CLI prints startup information with provider, model, and workspace
- the agent prints a `tool:` line before local file actions
- `hello.py` is created in the current workspace
- the assistant returns a final summary after the tool call finishes

If your API key is missing, invalid, or out of quota, the CLI should print a
clear error message instead of a Python traceback.

## Error Handling

The CLI now catches common provider/API failures and keeps the session alive.
Examples include:

- missing or invalid API key
- insufficient quota or rate limiting
- API timeout
- network connection failures
- generic provider API errors

Failed provider turns are rolled back from agent history so a broken request
does not pollute later turns.

## Safety Limitations

- File tools are restricted to the workspace root where the CLI starts.
- `edit_file` only supports creating files or replacing the first exact string match.
- Missing replacement text returns an error; the agent does not guess.
- This version does not execute shell commands.
- Review generated edits before using this on important code.

## Tests

```bash
pytest
```

Coverage:

```bash
pytest --cov=src/tiny_code_agent --cov-report=term-missing
```

The current suite covers the source tree at 100% line coverage.

## Roadmap

See [ROADMAP.md](ROADMAP.md).
