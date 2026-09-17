# Architecture

Legal Chunking is an extraction-agnostic, deterministic and explainable
document-structuring engine for legal texts. Its output is legal structure and
chunks, not retrieval results or legal advice.

## Current processing

`chunk_text` resolves a packaged profile and policy, normalizes input, assembles
sections, then builds chunks. `chunk_pdf` extracts and cleans PDF text through an
selected optional PDF adapter before entering the same text pipeline. Other extraction
systems can supply text directly; there is no public adapter registry or layout
input contract today. PyMuPDF is the default; PyMuPDF4LLM layout/OCR is explicitly
selected. See [extraction](extraction.md).

| Owner | Responsibility |
| --- | --- |
| `api.py` | Thin composition and Document result |
| `manifest.py`, `profiles.py`, `runtime_policy.py` | Packaged assets, aliases, policy resolution and runtime configuration |
| `normalize.py`, `legal_normalization.py` | Generic whitespace cleanup and marker-scoped numbering mechanics |
| `extract/backends.py`, `extract/models.py` | Extraction dispatch and neutral page-text boundary |
| `extract/pymupdf4llm*` | Optional isolated layout/OCR worker |
| `extract/pdf*` | Shared PDF candidate classification, page context and cleanup |
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
For statute chunking, asset `preferred_primary_units` chooses the first available
primary kind for the document. Descendant text is grouped with its primary section
for splitting; the original section list retains its own-text contract. Bare numeric
paragraph markers inside an article cannot open a higher-ranking section. Unowned
parent/preamble/schedule text remains independently preserved.

Typed metadata represents guidance points, rule blocks and definition entries
without inventing canonical hierarchy levels.

Policies are `default`, `statute`, `guidance` and `case_law`. Profile assets select
policy defaults and splitter behavior. Fallback budgets are character counts,
not tokens. They are not a universal maximum: guidance points and some typed
units intentionally remain whole even when oversized. Chunk metadata identifies
the chosen method, including `char_fallback` where used.

Numeric-script vocabulary, approved reference repairs and guidance candidate/artifact
patterns live in packaged `normalization_policy/` assets. Numbering markers and list/
range syntax have one profile owner. Manifest aliases supply document families with
word-boundary checks. Python applies these policies and sequencing; malformed runtime
configuration or unknown splitter names raise errors instead of silently downgrading.
Packaged JSON is cached with bounded keys and copied per caller; input texts are not
retained in this cache.

All five profiles (`generic`, `ru`, `us`, `eu`, `ae`) are enabled in the packaged
manifest. Support is bounded by document forms and test coverage; profile presence
does not imply complete jurisdiction coverage or current legal validity.

## Explainability and limitations

`trace=True` adds events from extract, normalize, detect, assemble and chunk
surfaces where instrumentation exists. CLI `explain` runs the same pipeline.
Every materialized chunk emits a boundary event with section, method and order.
Coverage is still partial: not every rejected candidate or deletion has an event, and stage labels do not imply chronologically sorted phases (policy
selection is emitted before normalization). Trace is runtime evidence, not model
reasoning; events can contain source text and need appropriate handling.

Section offsets refer to the processed text stream, not original PDF coordinates.
`Chunk.page` currently defaults to None; there is no end-to-end page/bounding-box
provenance contract. PDF cleanup can remove source material. Scanned-image OCR is optional and requires traineddata; recognition accuracy,
faithful table reconstruction and arbitrary layout recovery are not guaranteed.
The core cannot recover information discarded by an upstream extractor.

The base installation has no runtime dependencies. PDF dependencies remain
optional; no network, database, retrieval or LLM dependency belongs in the core.
