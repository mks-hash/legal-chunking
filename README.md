# legal-chunking

`legal-chunking` is an open-source Python library for structure-aware chunking of legal documents.

The project is intentionally focused on one narrow problem:

- ingest legal text from plain text and PDF sources
- normalize document text deterministically
- detect legal structure such as headings, articles, sections, items, and paragraphs
- split documents by logical boundaries instead of fixed character windows
- return stable chunks with structured metadata for downstream processing

## CLI

The package includes a small inspectable CLI:

```bash
legal-chunking chunk --text "Article 1. General provisions" --profile generic
legal-chunking structure --path ./rulebook.txt --profile ae --doc-kind primary_legislation
legal-chunking explain --path ./rulebook.pdf --profile ae --doc-kind primary_legislation
```

Command contracts:

- `chunk` emits chunk metadata only
- `structure` emits detected sections only
- `explain` emits staged trace events only

## Status

This repository is in early bootstrap stage.

Planned design principles:

- structure-aware chunking over naive sliding windows
- asset-driven profiles over hardcoded jurisdiction logic
- deterministic outputs for identical inputs
- pure library first, CLI second
- no vector database, no LLM orchestration, no application-specific runtime concerns

## Scope

Initial targets:

- Python package
- CLI entrypoint
- text and PDF inputs
- profile-based chunking behavior
- structured JSON export
- golden tests for legal chunk boundaries

Out of scope for v1:

- embeddings
- vector stores
- reranking
- LLM calls
- web services
- UI
- workflow orchestration

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
pytest
```

PDF extraction uses an optional dependency:

```bash
pip install legal-chunking[pdf]
```

## License

Apache-2.0
