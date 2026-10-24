# Tiny Code Agent

Tiny Code Agent is a small Python CLI coding agent inspired by Mihail Eric's
"How to Code Claude Code in 200 Lines of Code" article. It teaches the core
agent loop without hiding the moving parts:

1. send the user message to an LLM
2. let the model request a tool call
3. run that tool locally
4. send the tool result back
5. repeat until the model gives a final answer

The `v0.1` version supports these safe workspace-limited tools:

- `list_files`
- `list_tree`
- `search_files`
- `read_file`
- `preview_edit_file`
- `preview_append_file`
- `preview_insert_after`
- `preview_insert_before`
- `edit_file`
- `append_file`
- `insert_after`
- `insert_before`

It also includes:

- provider and model discovery with `--list-providers` and `--list-models`
- generated bash and zsh completion scripts
- clearer provider/API error messages instead of raw Python tracebacks
- lightweight terminal UX for interactive sessions, including colors and a small startup animation
- visible loading states while the agent waits on the model
- preview diffs before writes, so beginners can inspect the exact file change
- optional edit confirmations with `--confirm-edits`

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

To pause before writes during a learning session:

```bash
tiny-code-agent --confirm-edits
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

Type `exit` or `quit` to end the session. In an interactive terminal, the CLI
uses simple colors to distinguish user, tool, assistant, and error output.
It also shows a lightweight thinking line with request-aware phrases while
waiting on the model. Set `NO_COLOR=1` or pass `--plain` to disable ANSI colors
and animation.
In plain mode, the CLI prints `Assistant: Working...` every time it is waiting
on the model, including after local tool results. Pass `--confirm-edits` to
approve or reject each write.

If you accidentally type input like `You: exit`, the CLI strips the leading
`You:` prompt text automatically.

Session commands:

- `/help`
- `/models`
- `/workspace`
- `/exit`

## Learning Workflow

The safest way to learn how the agent edits code is to watch the tool trace:

1. Ask for a small change.
2. The model should inspect files with `read_file`.
3. Before writing, it can call `preview_edit_file`.
4. The CLI prints a unified diff showing removed lines with `-` and added lines with `+`.
5. If the diff looks right, the model can call `edit_file` to apply the same change.
6. With `--confirm-edits`, the CLI asks before the write is applied.
7. For end-of-file additions, the model can use `append_file` instead of replacing text.
8. For targeted additions, the model can use `insert_after` with an exact anchor.
9. For targeted prepends, the model can use `insert_before` with an exact anchor.

This mirrors a normal developer workflow: inspect, preview, then apply.
After one successful write, or if you reject a write, or if a write tool fails,
the current turn stops immediately. No extra write happens until you send a new
request.

## Try These Prompts

Run with confirmations enabled:

```bash
python -m tiny_code_agent --plain --confirm-edits
```

Then try:

```text
Show me a small tree of this project.
```

```text
Search for the hello function.
```

```text
Update hello.py so hello() returns "Hello from the smoke test".
```

```text
Append a short comment to the end of hello.py explaining that it is a smoke test file.
```

```text
Insert a comment before the print(hello()) line explaining why the script prints the greeting.
```

For write prompts, the expected learning loop is: inspect, preview a diff, ask
for confirmation, write only when you answer `y`, then stop the turn.

## Example

```text
You: Create hello.py with a hello function.
tool: preview_edit_file {"path": "hello.py", "old_str": "", "new_str": "..."}
  result: ok
  path: /path/to/workspace/hello.py
  diff:
    --- a/hello.py
    +++ b/hello.py
    +...
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
- Preview tools show unified diffs but do not write anything.
- `--confirm-edits` asks for an explicit `y` or `n` before write tools run.
  It is disabled by default.
- `edit_file` only supports creating files or replacing the first exact string match.
- `append_file`, `insert_after`, and `insert_before` only modify existing files.
- Successful, rejected, and failed write tools stop the current turn instead of
  continuing automatically.
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
