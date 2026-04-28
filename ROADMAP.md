# Tiny Code Agent Roadmap

## Beginner

1. Project scaffold with Python package, CLI entrypoint, README, tests, and GitHub-ready metadata.
2. Manual conversation loop with OpenAI.
3. Safe workspace-limited file tools: `list_files`, `read_file`, and `edit_file`.
4. Structured tool calling through the OpenAI Responses API.
5. `v0.1` release quality: docs, tests, `.env.example`, and clear safety limitations.

## Medium

6. Safer editing tools: append, insert before/after, dry-run diffs, and optional confirmations.
7. Search and inspection tools: text search, file metadata, and bounded tree views.
8. Guarded command execution for tests and read-only developer commands.
9. Planning mode for larger tasks before file mutation.

## Hard

10. Context management with long-file summaries and conversation compaction.
11. Provider abstraction for OpenAI first and Anthropic later.
12. Git-aware workflow with read-only status/diff helpers and confirmed mutations.
13. Optional local web UI with chat, tool timeline, and diff approvals.
14. Multi-agent workflows with planner, coder, reviewer, and test-fixer roles.
