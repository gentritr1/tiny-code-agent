# Skill Workflow

This repo includes Matt Pocock's project-local agent skills in `.agents/skills`.
Use skills only when they materially improve the work. Do not load a skill just
because it exists.

## Default Workflow

For most feature work:

1. Use `zoom-out` if the relevant code is unfamiliar.
2. Use `tdd` to add the feature with one behavior test at a time.
3. Use `diagnose` only if the implementation or tests fail in a non-obvious way.
4. Finish with normal verification: run tests, review `git diff`, then commit.

For planning work:

1. Use `grill-me` for important design choices that need pressure testing.
2. Use `to-prd` when the conversation should become a product requirements doc.
3. Use `to-issues` when a plan should become GitHub-ready implementation issues.

For token savings:

1. Use `caveman` when you want short, dense responses.
2. Turn it off by saying `stop caveman` or `normal mode`.

## Skill Guide

| Skill | Use When | Avoid When |
| --- | --- | --- |
| `zoom-out` | You need a map of unfamiliar code before editing. | The change is obvious and local. |
| `tdd` | Adding a feature or fixing behavior test-first. | You only need a quick explanation or docs update. |
| `diagnose` | Something is failing, flaky, slow, or hard to reproduce. | The problem is already understood and has a clear fix. |
| `caveman` | You want fewer tokens and concise technical answers. | You need careful explanation, onboarding, or nuanced tradeoffs. |
| `to-issues` | Turning a roadmap or plan into GitHub issues. | The work is small enough for one commit. |
| `to-prd` | Turning current context into a formal product spec. | The feature is already specified clearly. |
| `triage` | Managing GitHub issues through labels and readiness states. | We are not using issues yet. |
| `grill-me` | Stress-testing a plan through questions. | You already gave a decision-complete plan. |
| `grill-with-docs` | Stress-testing a plan against domain docs and ADRs. | The repo has no domain docs yet. |
| `improve-codebase-architecture` | Looking for deeper modules and refactoring opportunities. | Early v0.1 work where simple code is preferable. |
| `write-a-skill` | Creating a new custom skill. | We only need ordinary repo docs or scripts. |
| `setup-matt-pocock-skills` | Configuring repo-specific issue tracker and agent docs. | The default skill behavior is enough. |

## Prompt Examples

```text
Use zoom-out to explain how the tool loop works.
```

```text
Use tdd to add append_file.
```

```text
Use diagnose, pytest is failing.
```

```text
Use to-issues to break Phase 6 into GitHub issues.
```

```text
Use caveman mode for this task.
```

## Recommended Usage For This Project

- Beginner phases: use `tdd` for implementation, `diagnose` for failures.
- Medium phases: use `zoom-out` before touching larger areas, then `tdd`.
- Hard phases: use `grill-me` or `to-prd` before implementation.
- GitHub issue planning: use `to-issues` after a phase plan is accepted.

The agent should prefer the smallest useful skill. Loading fewer instructions
keeps context focused and reduces token waste.
