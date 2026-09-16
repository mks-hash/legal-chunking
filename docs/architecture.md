# Architecture

Legal Chunking is an extraction-agnostic, deterministic and explainable
document-structuring engine for legal texts. Its output is legal structure and
chunks, not retrieval results or legal advice.

## Current processing

`chunk_text` resolves a packaged profile and policy, normalizes input, assembles
sections, then builds chunks. `chunk_pdf` extracts and cleans PDF text through an
optional PyMuPDF adapter before entering the same text pipeline. Other extraction
systems can supply text directly; there is no public adapter registry or layout
input contract today.

| Owner | Responsibility |
| --- | --- |
| `api.py` | Thin composition and Document result |
| `manifest.py`, `profiles.py`, `runtime_policy.py` | Packaged assets, aliases, policy resolution and runtime configuration |
| `normalize.py` | Format-generic normalization preserving line boundaries |
| `extract/pdf*` | PDF extraction, candidate classification, page context and cleanup |
| `detect/heading*`, `detect/section*` | Heading candidates, admissibility and section assembly |
| `detect/guidance*`, `detect/definitions.py`, `detect/rulebook.py` | Specialized legal forms and metadata |
| `chunk/runtime.py`, `chunk/splitters.py` | Section selection, splitter registries, hashes and adjacency |
| `reference_parser.py`, `references.py`, `reference_context.py` | Separate structured reference analysis and normalization |
| `tracing/` | Optional structured events emitted by the actual runtime |

`detect/sections.py`, `detect/headings.py` and `chunk/legal.py` are facades over
staged implementation modules. Assembly currently lives in `detect/`; do not
create a parallel assembly layer solely to match a diagram.

## Structure and policy

Sections are a flat ordered list with parent IDs and paths, not a recursively
nested tree. Each section holds its own text; parent text does not aggregate all
children. The root may hold preamble text or be empty when headings start the text.
Typed metadata represents guidance points, rule blocks and definition entries
without inventing canonical hierarchy levels.

Policies are `default`, `statute`, `guidance` and `case_law`. Profile assets select
policy defaults and splitter behavior. Fallback budgets are character counts,
not tokens. They are not a universal maximum: guidance points and some typed
units intentionally remain whole even when oversized. Chunk metadata identifies
the chosen method, including `char_fallback` where used.

All five profiles (`generic`, `ru`, `us`, `eu`, `ae`) are enabled in the packaged
manifest. Support is bounded by document forms and test coverage; profile presence
does not imply complete jurisdiction coverage or current legal validity.

## Explainability and limitations

`trace=True` adds events from extract, normalize, detect, assemble and chunk
surfaces where instrumentation exists. CLI `explain` runs the same pipeline.
Coverage is partial: not every boundary, rejected candidate or deletion has an
event, and stage labels do not imply chronologically sorted phases (policy
selection is emitted before normalization). Trace is runtime evidence, not model
reasoning; events can contain source text and need appropriate handling.

Section offsets refer to the processed text stream, not original PDF coordinates.
`Chunk.page` currently defaults to None; there is no end-to-end page/bounding-box
provenance contract. PDF cleanup can remove source material. Scanned-image OCR,
faithful table reconstruction and arbitrary layout recovery are not guaranteed.
The core cannot recover information discarded by an upstream extractor.

The base installation has no runtime dependencies. PDF dependencies remain
optional; no network, database, retrieval or LLM dependency belongs in the core.
