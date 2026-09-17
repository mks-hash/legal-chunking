# Legal Chunking: repository instructions

Legal Chunking is an extraction-agnostic, deterministic and explainable
document-structuring engine for legal texts.

## Scope and architecture

- Keep structure assembly upstream of chunking. Character windows are an explicit
  fallback within a structural unit, not the primary legal boundary detector.
- The text engine must work without PDF dependencies. `chunk_pdf` is an optional
  PyMuPDF adapter; callers can extract text elsewhere and use `chunk_text`.
- Python owns mechanics, contextual admissibility and assembly; packaged JSON
  assets own profile vocabulary and policy selection. Extend the existing owner
  before introducing another strategy or abstraction.
- Regex may detect candidates. Avoid new context-free deletion/classification
  rules and scattered jurisdiction checks in shared runtime modules.
- Keep retrieval, ranking, embeddings, vector storage, LLMs, web services and
  product-specific orchestration outside this library.
- Preserve deterministic results for identical input, source name, profile,
  document kind, assets and runtime versions. No random or time-based identities.
  Content hashes and chunk identities have different meanings; see docs/api.md.
- Keep the public surface intentional; `src/legal_chunking/__init__.py` declares
  current exports. Do not expose implementation helpers accidentally.

## Find the owning contract

Start at [docs/README.md](docs/README.md). Read only the documents and skills needed
for the affected behavior:

- Engine, profiles, normalization, structure, references, IDs and trace:
  [.agents/skills/legal-engine/SKILL.md](.agents/skills/legal-engine/SKILL.md).
- Python implementation, tests, packaging and toolchain:
  [.agents/skills/python-library/SKILL.md](.agents/skills/python-library/SKILL.md).
- Before completing a substantial change or preparing a PR:
  [.agents/pre-pr-review.md](.agents/pre-pr-review.md).

Repository skills are Markdown workflows, not executable commands.
`pyproject.toml` owns package version, dependencies, Python and Ruff configuration.
Do not copy paths, services, identifier schemes or release claims from another repo.

## Change and validation discipline

Resolve contradictions at the owning behavior: code is evidence, tests enforce
contracts, documentation describes them. Do not weaken an assertion merely to make
an existing defect pass. Update relevant tests first; add tests for actual gaps.
Keep related docs, examples, assets and skills aligned with changed contracts.
Remove confirmed obsolete material rather than maintaining competing instructions.
Avoid unrelated refactors and broad unsafe autofixes.

Use the installed Python 3.14+ environment and commands in docs/development.md.
Run focused tests during implementation; run the full suite for structural,
normalization, asset or identity changes. Run Ruff lint and formatting checks for
Python changes. Report failures, missing tools and skipped PDF checks explicitly.
Do not equate a green synthetic suite with real-document parsing quality.

## Public and local material

`docs/`, tests/fixtures and repository instructions must be useful without
`.develop/`. `.develop/` is ignored local work: trackers, private notes, large PDF
fixtures and generated review outputs. Do not publish this corpus or copy private
product contracts into public docs. Keep small, redistributable regressions in
`tests/fixtures`; private PDF snapshots are not canonical golden expectations.

## Git and external actions

For GitHub/branch/PR/merge actions follow
[the GitHub contract](.github/AGENTS.override.md) together with these instructions.
`main` is the only trunk; historical `dev` is deprecated as a base/target.
Use `<type>/<short-kebab-case-description>` for branches, such as `feat/ocr-extraction`
or `fix/pdf-cleanup`; do not use the `codex/` prefix.

Inspect branch and working-tree state first; preserve unrelated user work.
Do not automatically switch/reset branches, pull, commit, push or open a PR just
because a local editing task is requested. For requested GitHub work inspect actual
remotes and live repository rules rather than assuming reviews or required CI.
Describe behavior, validation and limitations in the PR. Merge, publish and messages
to other people require authorization for that action; existing session authorization
persists. Do not weaken GitHub protections to perform an authorized merge.
