---
description: Review, self-check and commit current changes (Conventional Commits), no push
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*), Bash(uv run pytest:*), Bash(uv run ruff:*), Bash(uv run mypy:*)
---

# /commit

Commit current changes on demand (outside a full feature/debug flow).

1. Run `git status` and `git diff` to review changes.
2. Confirm tests pass (run `uv run pytest` if unsure) — do not commit failing tests.
3. Run `uv run ruff check . && uv run mypy src` and `uv run ruff format .`; fix warnings.
4. Self-review the diff per `.claude/rules/code-quality-review.md`.
5. Stage relevant files and write a Conventional Commits message per `.claude/rules/commit-style.md`. The summary line must make sense standalone to someone reading only the changelog later.
6. Commit. Do not push without explicit approval.
7. Regenerate CHANGELOG.md from commit history (e.g. git-cliff or conventional-changelog) — do not hand-write changelog entries.
