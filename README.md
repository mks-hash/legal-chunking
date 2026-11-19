# legal-chunking

[![Python validation](https://github.com/mks-hash/legal-chunking/actions/workflows/python-validation.yml/badge.svg)](https://github.com/mks-hash/legal-chunking/actions/workflows/python-validation.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)

Legal Chunking is an extraction-agnostic, deterministic and explainable
document-structuring engine for legal texts.

It normalizes text, recovers legal structure, builds chunks from legal boundaries,
and extracts structured citations. It is a Python library with an optional PDF
adapter and explicit layout/OCR support, not a retrieval or LLM framework.

## Status and scope

Alpha: package version `0.2.0`, Python 3.12+. The text core has no runtime
dependencies. PDF support uses the optional PyMuPDF extra; layout/OCR support uses the `ocr` extra
and separately installed Tesseract traineddata.

Enabled profiles: `generic`, `ru`, `us`, `eu`, `ae`. They support tested document
forms, not every legal text in a jurisdiction. Current capabilities include heading
hierarchy, guidance points, rule blocks, definition entries, policy-aware splitting,
starting-page provenance via `chunk_pages` / `chunk_pdf`, content hashes and optional runtime trace. Trace coverage is partial; faithful table reconstruction, OCR accuracy and
bounding-box/coordinate provenance are not guaranteed.

Retrieval, ranking, embeddings, vector stores, LLM reasoning, web services and
product workflows are outside the scope of this engine.

## Install and use

```bash
pip install legal-chunking
# Optional PDF support:
pip install 'legal-chunking[pdf]'
# Optional layout/OCR adapter (language data is installed separately):
pip install 'legal-chunking[ocr]'
```

```python
from legal_chunking import analyze_references, chunk_pdf, chunk_text, extract_references

# Text may come from any upstream extraction system.
document = chunk_text(
    "Article 1. Scope\n1. This Regulation applies to processing.\n"
    "2. See Article 6(1)(a) for lawful basis.",
    profile="eu",
    source_name="regulation.txt",
    trace=True,
)
# -> Chunk(order=1, chunk_method="statute_unit", section_type="article",
#          metadata=LegalMetadata(article_number="1", ...))

pdf_document = chunk_pdf(
    "rulebook.pdf", profile="ae", doc_kind="primary_legislation"
)
# An explicit OCR path, after installing the ocr extra and traineddata:
# scan_document = chunk_pdf("scan.pdf", backend="pymupdf4llm", ocr="auto",
#                           ocr_language="rus+eng")

analysis = analyze_references("пункты 1 и 3 статьи 450 ГК РФ", profile="ru")
# -> ReferenceOccurrence(start_offset=0, end_offset=23, raw="пункты 1 и 3 статьи 450",
#      references=(
#        ParsedReference(scheme="ru_article", article_number="450", paragraph_number="1", doc_family="gk_rf"),
#        ParsedReference(scheme="ru_article", article_number="450", paragraph_number="3", doc_family="gk_rf"),
#      ))
references = extract_references("пункт 3 статьи 450 ГК РФ", profile="ru")
```

Chunking returns a `Document` with normalized text, resolved profile/language,
selected policy, sections, chunks and optional trace. `assemble_sections` is also
exported for lower-level normalized-text assembly.

Determinism applies for identical inputs, arguments, assets and runtime versions.
Content hashes normalize whitespace; chunk IDs also depend on source identity,
structure, method and order. They are not permanent legal citation identifiers.
See [API contracts](docs/api.md) for signatures, metadata and serialization.

## CLI

```bash
legal-chunking chunk --text 'Article 1. General provisions' --profile generic
legal-chunking structure --path rulebook.txt --profile ae --doc-kind primary_legislation
legal-chunking explain --path rulebook.pdf --profile ae --doc-kind primary_legislation
legal-chunking review --path gdpr.pdf --profile eu --limit 12 --max-chars 220
legal-chunking review --path rulebook.pdf --profile ae --output snapshots/review.txt
```

`chunk` emits JSON chunk records including text; `structure` emits sections;
`explain` emits runtime trace; `review` emits human-readable previews (including `page=` when page provenance is available).
All commands accept `--text`, `--path` (text/PDF), or `--pages-json` (`[{"page_number": 1, "text": "..."}]`) and `--output`. PDF inputs also accept `--backend`, `--ocr`,
`--ocr-language` and `--ocr-dpi`; see [extraction](docs/extraction.md). The JSON format is not a frozen/versioned schema.

[Representative output samples](examples/output_samples/) illustrate selected
forms; they are not canonical golden fixtures or evidence of full corpus quality.

## Documentation and development

Start at [docs/README.md](docs/README.md) for architecture, API, development and
strategic roadmap. Repository agent instructions live in [AGENTS.md](AGENTS.md).

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
```

Small public fixtures live in `tests/fixtures/`. Large local PDFs and review outputs
live in the Git-ignored `.develop/testings/`; integration tests skip missing PDFs.
They are not part of the public repository. See [validation](docs/development.md)
for test ownership and release evidence.

## License

Apache-2.0
