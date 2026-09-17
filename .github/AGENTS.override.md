# GitHub and validation contract

Applies to `.github/**` and GitHub-related agent actions. Use with
[root instructions](../AGENTS.md).

## Branches and pull requests

- `main` is the only trunk and normal PR base/target. The historical `dev` branch
  is deprecated; do not base new work on it. It is unrelated to the Python `dev` extra.
- Normal flow: short-lived branch -> PR -> `main`.
- Name branches `<type>/<short-kebab-case-description>`, using the Conventional
  Commit types below. Examples: `feat/ocr-extraction`, `fix/pdf-cleanup`,
  `test/structure-contracts`, `docs/api-contracts`, `chore/github-workflow`.
  Do not use `codex/`, arbitrary agent names, or vague labels.
- Use `gh` for GitHub-side actions and `git` for local state.
- Keep one logical change per branch/PR. An explicitly requested integration may
  combine already reviewed local changes; describe the included commits and dependencies.
- Before renaming a remote branch, inspect PRs and verify its head. Use GitHub's
  branch rename API, then update local names/tracking refs and verify unchanged heads.
- User authorization to merge does not replace GitHub's required approval/checks.
  Do not disable protections or manufacture approval to complete a merge.

## Local Git safety

Before pull, merge or rebase, inspect:

```bash
git status --short --branch
git branch -vv
git rev-list --left-right --count HEAD...origin/main
```

Fetch when current remote state is needed. Preserve unrelated work. Do not run
plain `git pull` on divergent history. Use `git pull --ff-only` only when a
fast-forward is confirmed. On divergence, check whether commits are unique or
already upstream under another SHA before choosing reconciliation; do not reset
user work or create a merge commit merely to reconcile accidental divergence.

Inspect live repository rules and required reviews/checks before publishing or
merging a PR. Use a permitted merge method. After merge, fetch and synchronize
local `main` with a confirmed fast-forward, then verify the resulting tree.

## Commit and PR messages

Use Conventional Commits:

```text
<type>[optional scope]: <short imperative description>
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`,
`ci`, `build`, `revert`. Use a scope when useful, such as `core`, `extract`,
`references`, `assets`, `docs`, `tests`, `packaging` or `github`.
Avoid vague messages (`updates`, `fix stuff`, `wip`). PR titles follow the same
format; descriptions explain resulting behavior, reasons, validation and limitations.

Before opening/updating a PR, follow
[the repository review checklist](../.agents/pre-pr-review.md). Evaluate changes
to API, text/identity contracts and optional dependency behavior. `pyproject.toml`
owns the package version; an ordinary edit or merge does not automatically publish
or bump a release. Document compatibility changes and keep pre-alpha claims honest.

## Validation and CI

Follow [development validation](../docs/development.md). Python/packaging/tooling
changes use [python-library](../.agents/skills/python-library/SKILL.md); engine,
profile, reference or identity changes additionally use
[legal-engine](../.agents/skills/legal-engine/SKILL.md).

No checked-in CI workflow currently exists. Do not claim CI coverage or require a
nonexistent `repo-contracts.yml` or another project's skills/scripts. If introducing
CI, use this repository's Python version, actual pytest/Ruff commands and packaging
contracts; report absent optional PDF/OCR fixtures as skips, not fidelity evidence.
Never weaken checks to obtain green status. Keep CI, docs and validation commands
aligned when they change. Large/private fixtures remain outside Git in `.develop/`.
