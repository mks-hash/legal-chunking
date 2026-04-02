# legal-chunking Implementation Plan

## Goal

Build a principal-level open-source Python library for deterministic, structure-aware chunking of legal documents.

The library must remain a standalone project. It may use SolvenX as a design reference, but it must not copy private runtime code or inherit SolvenX application concerns.

## Product Boundary

`legal-chunking` is responsible for:

- plain text and PDF input handling
- deterministic text normalization
- structure detection for legal documents
- logical chunking by structural boundaries
- chunk metadata and stable identifiers
- asset-driven jurisdiction profiles
- JSON export and CLI ergonomics
- evaluation fixtures for chunk quality and determinism

`legal-chunking` is explicitly not responsible for:

- embeddings
- vector databases
- retrieval orchestration
- query routing
- LLM integration
- web search
- application storage runtimes
- case lifecycle or product workflows

## Canonical Design Principles

The implementation should preserve these principles from the SolvenX ingestion canon without importing product-specific concerns:

1. Structure-first, not plain-text-first.
2. Deterministic outputs for identical inputs.
3. Asset-driven policies instead of hardcoded jurisdiction branches in Python.
4. Fallback chunking is degraded-only, not the primary path.
5. Extraction, normalization, section parsing, and chunking must form one explicit pipeline.
6. Chunk metadata must stay traceable to profile, policy version, and pipeline version.

## Repository Architecture

Planned package shape:

```text
src/legal_chunking/
  api.py
  models.py
  cli.py
  normalize.py
  hashing.py
  manifest.py
  profiles.py
  extract/
  detect/
  chunk/
  export/
  eval/
  assets/
tests/
examples/
docs/
```

Architecture rules:

- `api.py` exposes the public library surface only.
- `models.py` owns stable OSS-facing document, section, and chunk models.
- `extract/` handles source-to-text extraction boundaries.
- `normalize.py` stays format-generic and deterministic.
- `detect/` owns heading, numbering, and section-boundary detection.
- `chunk/` owns chunk assembly only.
- `assets/` owns profile manifests, heading patterns, numbering markers, and chunking policy.
- `eval/` owns golden tests and chunk-quality metrics, not runtime logic.

## Asset Model

The OSS library should use four asset layers from day one:

1. `manifest`
   - profile registry
   - aliases
   - enabled state
   - policy versions
2. `heading_patterns`
   - regex patterns for canonical hierarchy candidates
3. `numbering_markers`
   - lexical numbering families by profile
4. `chunking_policy`
   - structure priorities
   - fallback thresholds
   - policy labels such as `statute`, `guidance`, `case_law`, `default`

The engine must resolve behavior through assets first. Python code should implement parsing mechanics and safety guards, not jurisdiction policy tables.

## Public API Target

The first stable API target remains intentionally small:

```python
from legal_chunking import chunk_pdf, chunk_text

doc = chunk_text(text, profile="ru")
doc = chunk_pdf("contract.pdf", profile="generic")
```

Possible future API additions must not weaken this simplicity.

## Data Model Target

### Document

- `source_name`
- `profile`
- `language`
- `text`
- `sections`
- `chunks`

### Section

- `section_id`
- `kind`
- `title`
- `order`
- `article_number`
- `paragraph_number`
- `start_offset`
- `end_offset`

### Chunk

- `chunk_id`
- `text`
- `order`
- `page`
- `section_id`
- `section_title`
- `article_number`
- `paragraph_number`
- `semantic_hash`

Near-term additive metadata that should be introduced early:

- `prev_chunk_id`
- `next_chunk_id`
- `profile_version`
- `pipeline_version`

## Profiles

Profiles for v1:

- `generic`: fully supported
- `ru`: fully supported
- `us`: minimal scaffold
- `eu`: minimal scaffold

Profile responsibilities:

- aliases and manifest resolution
- heading patterns
- numbering markers
- chunk-policy selection
- language hints

The engine must never assume RU-only legal structure.

## Implementation Phases

### Phase 0: Repository Bootstrap

Outcome:

- standalone repo
- packaging baseline
- CLI scaffold
- tests and linting baseline

Status: complete.

### Phase 1: Deterministic Core Pipeline

Outcome:

- `normalize.py`
- `hashing.py`
- core models finalized for v1 alpha
- explicit pipeline versioning
- deterministic `chunk_text()` behavior

Deliverables:

- extracted-text normalization contract
- chunk-text normalization contract
- semantic hash function
- stable chunk ordering and adjacency

### Phase 2: Asset Runtime

Outcome:

- manifest loader
- profile resolution
- packaged asset layout
- schema validation for assets

Deliverables:

- `assets/manifest.v1.json`
- profile-specific heading patterns
- profile-specific numbering markers
- profile-specific chunking policy files

### Phase 3: Structure Detection

Outcome:

- heading detection
- numbering-family detection
- section-tree assembly
- safe fallback rules

Deliverables:

- `detect/headings.py`
- `detect/numbering.py`
- `detect/sections.py`
- parser guards preventing false-positive headings from swallowing body text

### Phase 4: Chunk Assembly

Outcome:

- structure-aware chunk builder
- degraded fallback paragraph chunking
- adjacency metadata

Deliverables:

- `chunk/legal.py`
- `chunk/fallback.py`
- profile-aware chunk policy resolution

### Phase 5: PDF Extraction

Outcome:

- deterministic PDF extraction boundary
- page-aware payload support where available

Deliverables:

- `extract/pdf.py`
- extractor interface with one default implementation
- optional page provenance propagated into chunk metadata

Design note:

- v1 should start with one dependable PDF backend, not a multi-backend extraction matrix.
- Adding alternative extractors later is acceptable if the extraction contract remains stable.

### Phase 6: Evaluation and Golden Fixtures

Outcome:

- jurisdiction fixtures
- determinism tests
- boundary-quality metrics

Deliverables:

- golden fixtures for `generic` and `ru`
- smoke fixtures for `us` and `eu`
- chunk-boundary regression tests
- parser false-positive tests

### Phase 7: OSS Hardening

Outcome:

- examples
- API docs
- contribution guide
- release workflow

Deliverables:

- richer README
- examples directory
- changelog policy
- CI workflow

## PR-Sized Roadmap

The project should move in small, reviewable slices.

1. `feature/normalize-and-hash`
   - add normalization module
   - add hashing module
   - extend models with adjacency and pipeline metadata
   - add determinism tests
2. `feature/assets-runtime`
   - add manifest and profile resolution
   - add `generic`, `ru`, `us`, `eu` assets
   - validate asset loading
3. `feature/heading-detection`
   - add heading-pattern compilation and detection
   - add section model assembly for text input
4. `feature/chunk-assembly`
   - add structure-aware chunk builder
   - add degraded fallback chunker
5. `feature/pdf-extraction`
   - add PDF extraction boundary and tests
6. `feature/golden-fixtures`
   - add evaluation fixtures and regression metrics
7. `feature/cli-json-export`
   - extend CLI and export surface
8. `feature/ci-release-bootstrap`
   - add GitHub Actions, packaging checks, and release docs

## Immediate Next Slice

The next implementation slice should be `feature/normalize-and-hash`.

That slice should:

- create `normalize.py`
- create `hashing.py`
- move placeholder chunk generation to normalized deterministic output
- add `prev_chunk_id` and `next_chunk_id`
- introduce `pipeline_version`
- add tests for normalization determinism and semantic-hash stability

This is the right first build slice because every later parser and chunker layer depends on stable normalization and hashing contracts.

## Quality Gates

Every feature slice should keep these checks green:

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

Near-term additions:

```bash
.venv/bin/python -m build
```

## Extraction Rules from SolvenX Reference

These are allowed influences:

- structure-first extraction and chunking
- asset-driven heading policies
- deterministic normalization discipline
- traceable chunk metadata
- legal-unit-aware chunk boundaries

These must not be copied into OSS scope:

- SolvenX storage layouts
- Qdrant payload contracts
- application case semantics
- private ingestion service orchestration
- runtime-specific legal retrieval logic
- query taxonomy and routing policy assets

## Definition of Done for v1 Alpha

`legal-chunking` reaches v1 alpha when all of the following are true:

1. `chunk_text()` is deterministic and structure-aware for `generic` and `ru`.
2. `chunk_pdf()` produces deterministic output from a supported PDF backend.
3. Asset profiles control parsing behavior without RU-only engine branches.
4. Golden tests cover realistic legal fixtures and edge cases.
5. CLI JSON output is stable enough for downstream tooling.
6. The package is publishable without any SolvenX-private dependency or code coupling.
