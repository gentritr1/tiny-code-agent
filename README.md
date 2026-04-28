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
export TINY_CODE_AGENT_MODEL="gpt-5.5"
```

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

Type `exit` or `quit` to end the session.

## Example

```text
You: Create hello.py with a hello function.
tool: edit_file {"path": "hello.py", "old_str": "", "new_str": "..."}
Assistant: Created hello.py with a hello function.
```

The exact tool trace depends on the model, but the loop is always the same:
the model asks for tools, the CLI runs them, and the model receives structured
results.

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

## Roadmap

See [ROADMAP.md](ROADMAP.md).
