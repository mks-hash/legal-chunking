# legal-chunking

`legal-chunking` is an open-source Python library for deterministic, structure-aware parsing, chunking, and reference extraction for legal documents.

The project is intentionally narrow:

- accept legal text from plain text and PDF sources
- normalize text deterministically
- recover legal structure such as headings, parts, sections, articles, clauses, and points
- build chunks from logical legal boundaries instead of fixed-size windows
- return stable metadata and reference parsing results for downstream systems

It is not a retrieval framework, ranking engine, or product orchestration layer.

## Why Not Generic Text Splitters?

Most text splitters operate on fixed-size windows or shallow heuristics.

`legal-chunking` is designed to preserve legal structure instead of flattening it:

- reconstructs legal structure before chunking instead of treating text as flat token sequences
- uses semantic legal boundaries such as articles, sections, rules, and guidance points as the primary split strategy
- preserves deterministic and reproducible outputs for identical inputs
- exposes explainable trace data for the chunking pipeline

The goal is not to be smaller than generic splitters.
The goal is to be narrower in scope, but stronger inside that scope.

## Public API

The public package surface is intentionally small:

```python
from legal_chunking import chunk_pdf, chunk_text, extract_references

doc = chunk_text(
    "Article 1. General provisions\nThe borrower shall...",
    profile="generic",
)

pdf_doc = chunk_pdf(
    "./rulebook.pdf",
    profile="ae",
    doc_kind="primary_legislation",
)

refs = extract_references(
    "пункт 3 статьи 450 ГК РФ",
    profile="ru",
)
```

Core public types:

- `ParsedReference`
- `Document`
- `Section`
- `Chunk`

Chunking APIs return a `Document` that contains:

- normalized `text`
- resolved `profile` and `language`
- selected `chunk_policy`
- `sections`
- `chunks`
- optional `trace`

## Examples: Structural Precision

`legal-chunking` preserves legal hierarchy across jurisdictions. Below are representative outputs for different document families:

### US Federal Rules (FRCP)
Reconstructs deep rule subdivisions (`Rule 4(a)(1)(A)`) even when they span multiple lines.

```json
{
  "profile": "us",
  "chunks": [
    {
      "chunk_id": "chunk-394c5793d613",
      "text": "Rule 4. Summons (a) CONTENTS; AMENDMENTS. (1) Contents...",
      "section_title": "Rule 4. Summons",
      "section_type": "article",
      "metadata": { "article_number": "4" }
    }
  ]
}
```

### EU GDPR (Recitals)
Automatically groups preamble recitals into semantic blocks instead of treating them as raw introductory text.

```json
{
  "profile": "eu",
  "chunks": [
    {
      "chunk_id": "chunk-d3289eb5515e",
      "text": "(1) The protection of natural persons... (2) The principles of...",
      "section_title": "Document",
      "section_type": "document_root"
    }
  ]
}
```

### RU Consumer Review (Case References)
Extracts detailed court references directly from the legal unit headers.

```json
{
  "profile": "ru",
  "chunks": [
    {
      "chunk_id": "chunk-48ca2b1d622c",
      "text": "17. Банк как выгодоприобретатель...",
      "section_title": "Point 17",
      "section_type": "review_point",
      "metadata": {
        "legal_unit_type": "guidance_point",
        "source_case_number": "18-КГ23-155-К4",
        "source_case_court": "Верховный Суд РФ"
      }
    }
  ]
}
```

Full representative samples are available in the [examples/output_samples/](./examples/output_samples/) directory.

## CLI

The package includes a small inspectable CLI:

```bash
legal-chunking chunk --text "Article 1. General provisions" --profile generic
legal-chunking structure --path ./rulebook.txt --profile ae --doc-kind primary_legislation
legal-chunking explain --path ./rulebook.pdf --profile ae --doc-kind primary_legislation
legal-chunking review --path ./documents/gdpr.pdf --profile eu --limit 12
legal-chunking review --path ./rulebook.pdf --profile ae --output ./snapshots/rulebook-review.txt
```

Command contracts:

- `chunk` emits chunk metadata only
- `structure` emits detected sections only
- `explain` emits staged trace events only
- `review` emits a human-readable section and chunk preview for manual inspection

For real-document review, `review` is the fastest way to inspect chunk quality by eye:

```bash
legal-chunking review --path ./documents/us_federal_rules.pdf --profile us --limit 15 --max-chars 220
legal-chunking review --path ./documents/vara_rules.pdf --profile ae --doc-kind primary_legislation --limit 20
legal-chunking review --path ./documents/ru_plenum.pdf --profile ru --doc-kind court_guidance --limit 25
```

That output lets you inspect:

- detected section titles and order
- chunking method per chunk
- short text previews for each chunk
- total section and chunk counts per document

All CLI commands also support `--output` for snapshot export.
Use that for reproducible manual review and diffable artifacts:

```bash
mkdir -p ./snapshots

legal-chunking review \
  --path ./documents/gdpr.pdf \
  --profile eu \
  --limit 20 \
  --max-chars 220 \
  --output ./snapshots/gdpr-eu-review.txt

legal-chunking review \
  --path ./documents/us_federal_rules.pdf \
  --profile us \
  --limit 20 \
  --max-chars 220 \
  --output ./snapshots/frcp-us-review.txt

legal-chunking review \
  --path ./documents/vara_rules.pdf \
  --profile ae \
  --doc-kind primary_legislation \
  --limit 20 \
  --max-chars 220 \
  --output ./snapshots/vara-ae-review.txt

legal-chunking review \
  --path ./documents/ru_consumer_review.pdf \
  --profile ru \
  --doc-kind court_guidance \
  --limit 25 \
  --max-chars 220 \
  --output ./snapshots/consumer-review-ru-review.txt

legal-chunking review \
  --path ./documents/ru_plenum.pdf \
  --profile ru \
  --doc-kind court_guidance \
  --limit 25 \
  --max-chars 220 \
  --output ./snapshots/plenum-ru-review.txt
```

## CLI

The package includes a small inspectable CLI:

```bash
legal-chunking chunk --text "Article 1. General provisions" --profile generic
legal-chunking structure --path ./rulebook.txt --profile ae --doc-kind primary_legislation
legal-chunking explain --path ./rulebook.pdf --profile ae --doc-kind primary_legislation
legal-chunking review --path ./documents/gdpr.pdf --profile eu --limit 12
legal-chunking review --path ./rulebook.pdf --profile ae --output ./snapshots/rulebook-review.txt
```

Command contracts:

- `chunk` emits chunk metadata only
- `structure` emits detected sections only
- `explain` emits staged trace events only
- `review` emits a human-readable section and chunk preview for manual inspection

For real-document review, `review` is the fastest way to inspect chunk quality by eye:

```bash
legal-chunking review --path ./documents/us_federal_rules.pdf --profile us --limit 15 --max-chars 220
legal-chunking review --path ./documents/vara_rules.pdf --profile ae --doc-kind primary_legislation --limit 20
legal-chunking review --path ./documents/ru_plenum.pdf --profile ru --doc-kind court_guidance --limit 25
```

That output lets you inspect:

- detected section titles and order
- chunking method per chunk
- short text previews for each chunk
- total section and chunk counts per document

All CLI commands also support `--output` for snapshot export.
Use that for reproducible manual review and diffable artifacts:

```bash
mkdir -p ./snapshots

legal-chunking review \
  --path ./documents/gdpr.pdf \
  --profile eu \
  --limit 20 \
  --max-chars 220 \
  --output ./snapshots/gdpr-eu-review.txt

legal-chunking review \
  --path ./documents/us_federal_rules.pdf \
  --profile us \
  --limit 20 \
  --max-chars 220 \
  --output ./snapshots/frcp-us-review.txt

legal-chunking review \
  --path ./documents/vara_rules.pdf \
  --profile ae \
  --doc-kind primary_legislation \
  --limit 20 \
  --max-chars 220 \
  --output ./snapshots/vara-ae-review.txt

legal-chunking review \
  --path ./documents/ru_consumer_review.pdf \
  --profile ru \
  --doc-kind court_guidance \
  --limit 25 \
  --max-chars 220 \
  --output ./snapshots/consumer-review-ru-review.txt

legal-chunking review \
  --path ./documents/ru_plenum.pdf \
  --profile ru \
  --doc-kind court_guidance \
  --limit 25 \
  --max-chars 220 \
  --output ./snapshots/plenum-ru-review.txt
```

## Status

This repository is in pre-alpha.
The current implementation already includes:

- packaged manifest-driven profiles
- deterministic normalization and semantic hashing
- section assembly with typed legal units
- policy-aware chunking
- PDF extraction support
- structured legal reference extraction
- CLI commands for chunk, structure, and explain

Design principles:

- structure-aware chunking over naive sliding windows
- asset-driven profiles over hardcoded jurisdiction logic
- deterministic outputs for identical inputs
- inspectable runtime behavior
- dependency-light core with explicit optional extras

## Scope

In scope for v1:

- text and PDF inputs
- profile resolution by code or alias
- policy-aware chunking
- structured legal reference extraction
- traceable boundary decisions
- structured JSON output through the CLI

Out of scope for v1:

- embeddings
- vector stores
- retrieval orchestration
- reranking
- LLM reasoning
- web services
- UI
- workflow orchestration

## Profiles

Profiles currently enabled through the packaged manifest:

- `generic`
- `ru`
- `us`
- `eu`
- `ae`

`generic` and `ru` are the primary working profiles.
`us`, `eu`, and `ae` are narrower but real runtime profiles, not placeholder names.

## Repository Layout

```text
src/legal_chunking/
tests/
examples/
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q
ruff check .
ruff format --check .
```

PDF extraction uses an optional dependency:

```bash
pip install legal-chunking[pdf]
```

PDF extraction uses an optional dependency:

```bash
pip install legal-chunking[pdf]
```

## License

Apache-2.0
