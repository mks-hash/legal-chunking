---
name: python-library
description: Implement, test or package Python changes in Legal Chunking using its actual src layout, optional PDF extra and pytest/Ruff configuration.
---

# Python library workflow

Read root AGENTS.md and docs/development.md. pyproject.toml owns the Python minimum
(3.14), package version, dependencies, Hatchling backend and Ruff settings.
Use the installed project environment; do not import another repo's Docker,
frontend, service, type-checker or MCP workflow.

Keep public composition thin, result dataclasses explicit and import-time behavior
quiet. Do not configure global logging. Keep dynamic asset data localized at
load/validation boundaries rather than widening unrelated types to silence errors.
Use named library errors where applicable; do not silently swallow IO or policy
failures. Core text imports must not require PyMuPDF or network/service dependencies.

Install editable with the dev extra when environment setup is required. For an
existing .venv use its Python directly or activate it. Validation commands:

```bash
python -m pytest -q tests/test_api.py  # replace with the affected existing subset
python -m ruff check src tests
python -m ruff format --check src tests
```

Run the full suite for broad/core contract changes. Do not automatically install
new tools or add wrappers where these commands suffice. Report missing tools,
failures and skipped corpus tests; no checked-in CI currently guarantees parity.

Use current official upstream docs if installed versions/configuration do not
resolve a version-sensitive question. Do not change architecture to follow a
framework convention or bump package versions for ordinary edits.

For packaging changes follow the release evidence procedure in
 docs/development.md: inspect wheel/sdist assets, install into a clean environment,
exercise text/reference APIs without PDF and test optional PDF/CLI separately.
Existing dist/ artifacts do not validate the current source tree.
