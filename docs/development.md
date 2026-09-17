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

The dev extra includes pytest, Ruff, PyMuPDF and PyMuPDF4LLM. Base text usage has no runtime
dependencies; PDF users install `legal-chunking[pdf]`; layout/OCR users install
`legal-chunking[ocr]` and supply Tesseract traineddata. Tested versions for this change
are PyMuPDF/PyMuPDF4LLM 1.28.2, pytest 9.1.1 and Ruff 0.16.6. Use repository-defined
versions and official upstream documentation for unresolved version-sensitive
behavior. No Docker, frontend, MCP or hosted-service setup is required here.

## Test ownership

| Tests | Main contract |
| --- | --- |
| `test_quality_contracts.py` | Independently authored structure/text expectations and offset/identity scenarios |
| `test_tracing.py` | Actual decision reasons, source planes, output invariance and repeatability |
| `test_api.py` | API, normalization, hashes, chunk methods, synthetic PDF cleanup, trace and CLI |
| `test_sections.py`, `test_headings.py` | Hierarchy, candidate admissibility and legal forms |
| `test_profiles.py` | Manifest, aliases, policy defaults and reference families |
| `test_references.py` | Citation normalization and structured parsing |
| `test_reference_occurrences.py` | Original/normalized input ranges, repeated occurrences, grouped lists and shared family restrictions |
| `test_real_pdfs.py` | Optional local integration corpus across EU/US/AE/RU |

Run focused tests while changing behavior, then the full suite for pipeline,
asset or identity changes. Assert meaningful structure, metadata and preserved
text, not just counts. Add small public fixtures only with redistribution rights;
update existing tests where they already own the regression.

The public suite includes synthetic PDFs and layout extraction and therefore
requires the dev extra.
Real PDF tests look in `.develop/testings/` and skip when individual files are
missing. A fresh clone does not contain these PDFs. Report passed and skipped
checks separately; skipping the corpus does not validate real-document quality.
The local scanned-PDF integration test looks for
`.develop/testings/ocr-data/eng.traineddata` and explicitly skips when absent. It
checks real recognition, source immutability, repeated results, blank pages and clean
CLI JSON. The runtime does not depend on this local path: callers supply traineddata
through their own `TESSDATA_PREFIX`.

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
## Continuous integration

[Python validation](../.github/workflows/python-validation.yml) runs on PRs targeting
`main`, pushes to `main`, and manual dispatch with Python 3.14 on Ubuntu.

- **Tests and Ruff:** installs the dev extra, runs lint/format and pytest with `-ra`
  so missing local PDFs/traineddata are reported as skips. Synthetic native/layout
  PDF checks run; CI does not download the private corpus or OCR models.
- **Installed core and distribution:** builds wheel/sdist, checks runtime assets
  and private-material exclusion, installs the wheel without extras, then runs
  text quality/reference contracts and the console entrypoint outside the checkout. The one
  synthetic native PDF quality test is excluded only from this core job and runs
  in the dev job. This also checks that PDF packages are absent.

These checks do not certify real-document fidelity or installed-wheel OCR behavior;
local release evidence remains necessary. Actions are pinned to official release
commit SHAs, use read-only repository permissions and do not persist credentials.
The stable job names above can be selected as required checks in the `main` ruleset
after GitHub has observed a successful run. Adding this workflow does not itself
change ruleset requirements or publish a package.

## GitHub workflow

`main` is the only trunk. Use a short-lived `<type>/<description>` branch and a PR
into `main`; `dev` is historical and must not be used as a new base/target. Branch
names, Conventional Commit messages, synchronization and GitHub approval rules are
owned by [the GitHub contract](../.github/AGENTS.override.md).
This branch policy does not change the Python `dev` installation extra.
