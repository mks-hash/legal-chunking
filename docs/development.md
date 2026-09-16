# Development and validation

## Environment

Use Python 3.14 or newer, as required by pyproject.toml:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
```

The dev extra includes pytest, Ruff and PyMuPDF. Base text usage has no runtime
dependencies; PDF users install `legal-chunking[pdf]`. Use repository-defined
versions and official upstream documentation for unresolved version-sensitive
behavior. No Docker, frontend, MCP or hosted-service setup is required here.

## Test ownership

| Tests | Main contract |
| --- | --- |
| `test_api.py` | API, normalization, hashes, chunk methods, synthetic PDF cleanup, trace and CLI |
| `test_sections.py`, `test_headings.py` | Hierarchy, candidate admissibility and legal forms |
| `test_profiles.py` | Manifest, aliases, policy defaults and reference families |
| `test_references.py` | Citation normalization and structured parsing |
| `test_real_pdfs.py` | Optional local integration corpus across EU/US/AE/RU |

Run focused tests while changing behavior, then the full suite for pipeline,
asset or identity changes. Assert meaningful structure, metadata and preserved
text, not just counts. Add small public fixtures only with redistribution rights;
update existing tests where they already own the regression.

The public suite includes synthetic PDFs and therefore requires the dev extra.
Real PDF tests look in `.develop/testings/` and skip when individual files are
missing. A fresh clone does not contain these PDFs. Report passed and skipped
checks separately; skipping the corpus does not validate real-document quality.
Existing local PDF assertions can fail independently of the synthetic suite;
investigate source, extraction and structure before changing expected output.

## Local review

`.develop/` is ignored. Keep trackers, private notes, large source PDFs and
regenerable outputs there. Export into a new run directory so historical
snapshots remain distinguishable:

```bash
legal-chunking review --path .develop/testings/CELEX_32016R0679_EN_TXT.pdf \
  --profile eu --limit 20 --output .develop/testings/current/gdpr-review.txt
legal-chunking explain --text 'Article 1. Scope' --profile generic
```

For quality review compare source and output: missing legal text, false headings,
subdivision ownership, repeated headers, definitions, fallback methods and trace.
A passing count threshold or a historical export is not proof of fidelity.

## Release evidence

Before declaring a release ready, verify tests, Ruff, documented limitations and
representative quality. Build wheel and sdist with `python -m build` (install the
build frontend separately if needed). Inspect archive contents for packaged JSON
assets and absence of private .develop material. Install the wheel into a clean
environment, exercise text/reference APIs without PDF extras, then PDF support
with the extra. Test CLI from that installed artifact. Record versions and checks.
Existing dist files or historical readiness notes are not current evidence.
There is currently no checked-in CI workflow; local checks are not a CI claim.
