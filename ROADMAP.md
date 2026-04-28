# Tiny Code Agent Roadmap

## Beginner

1. Done: project scaffold with Python package, CLI entrypoint, README, tests, and GitHub-ready metadata.
2. Done: manual conversation loop with OpenAI.
3. Done: safe workspace-limited file tools: `list_files`, `read_file`, and `edit_file`.
4. Done: structured tool calling through the OpenAI Responses API.
5. Done: `v0.1` release quality: docs, tests, `.env.example`, and clear safety limitations.
6. Done: provider and model discovery commands plus generated shell completions.
7. Done: beginner-friendly terminal UX with colored labels and graceful provider error handling.
8. Done: automated coverage tooling with 100% line coverage for `src/tiny_code_agent`.

## Medium

9. Safer editing tools: append, insert before/after, dry-run diffs, and optional confirmations.
10. Search and inspection tools: text search, file metadata, and bounded tree views.
11. Guarded command execution for tests and read-only developer commands.
12. Planning mode for larger tasks before file mutation.

## Hard

13. Context management with long-file summaries and conversation compaction.
14. Expand provider support beyond OpenAI while keeping the current adapter boundary.
15. Git-aware workflow with read-only status/diff helpers and confirmed mutations.
16. Optional local web UI with chat, tool timeline, and diff approvals.
17. Multi-agent workflows with planner, coder, reviewer, and test-fixer roles.
