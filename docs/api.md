# API and result contracts

The package version is `0.1.0` in `pyproject.toml`; this is pre-alpha. The current
API and serialization are documented behavior, not a frozen v1 schema.

## Public package exports

`legal_chunking.__all__` exports:

- `chunk_text`, `chunk_pdf`, `assemble_sections`, `extract_references`;
- `Document`, `Section`, `Chunk`, `ParsedReference`;
- `LegalChunkingError`, `AssetConfigError`, `InvalidProfileError`,
  `PdfDependencyError`, `ExtractionError`.

```python
from dataclasses import asdict
from legal_chunking import chunk_text, extract_references

document = chunk_text(
    "Article 1. Scope\nThis act applies to contracts.",
    profile="generic",
    source_name="example.txt",
    doc_kind="primary_legislation",
    trace=True,
)
payload = asdict(document)
references = extract_references("пункт 3 статьи 450 ГК РФ", profile="ru")
```

`chunk_text(text, profile="generic", source_name="<memory>", doc_kind=None,
trace=False)` returns Document. `chunk_pdf(path, profile="generic", doc_kind=None,
trace=False, *, backend="pymupdf", ocr="off", ocr_language="eng", ocr_dpi=300)` returns the same model and uses the file basename as
source_name.

`assemble_sections(text, *, profile="generic", chunk_policy="default",
doc_kind=None, source_name="<memory>", trace=None)` returns sections. This lower
level API expects normalized text and an explicit policy; it does not perform the
high-level API's normalization/policy selection. Its trace parameter is an internal
collector, not the high-level boolean.

`extract_references(text, *, profile="generic", doc_family=None)` returns ParsedReference objects.
An explicit doc_family narrows family-scoped matching and must name a family in
the selected profile manifest; unrelated/unknown families raise ValueError. A known
local source conflicting with that restriction is excluded, never relabelled. Reference analysis has
additional citation-only repairs, separate from the canonical
text view. Both paths share marker-scoped numeric-script mechanics. `raw` reflects
the parser's normalized matching text, not guaranteed verbatim source bytes.
Coordinated RU article/part/point lists inherit their explicit article container;
three-level point numbers are preserved. Ranges remain range strings (for example
`3–4`); they are not expanded into invented discrete references. Chapter references
use `scheme="chapter"`; the historical `article_number` field holds their number.
Likewise `paragraph_number` is the legacy slot for RU points, not a complete typed
locator chain. Subpoint/ordinal-paragraph roles and occurrence offsets are not a
full supported address model yet. Results deduplicate canonical components rather
than preserving every occurrence.

Parenthesized EU/US citation identifiers remain parenthesized; they are not RU dotted
suffixes. RU merged-digit repair is restricted to an asset-approved map, not an
arbitrary last-digit split. These OCR/reference repairs are not applied wholesale
to document body text. Normalization does not verify numbering against current law.

References identify citation components and optional document family; they do not
resolve a citation to an authoritative document, edition or legal validity.
Use `to_dict()` or `to_canonical_parts(jurisdiction=...)` for reference payloads.

Profile codes or aliases resolve through the manifest. Unknown/disabled profiles
raise InvalidProfileError. Unknown doc_kind values currently select the asset's
`other` policy, then `code`, rather than raising a validation error. Missing PDF/OCR
packages or traineddata raise PdfDependencyError. Layout worker
failures raise ExtractionError without exposing raw upstream diagnostic payloads.
Unsupported backend/mode combinations raise ValueError; asset failures use
AssetConfigError. Ordinary
IO and some configuration errors may still be standard Python exceptions.

## Results and identity

Document contains source_name, resolved profile, language, normalized text,
chunk_policy, sections, chunks and optional trace. Section contains hierarchy,
metadata, processed-text offsets and text. Chunk contains text, method, section
association, legal metadata, semantic_hash and previous/next chunk IDs.
The models are dataclasses; they are not frozen schema/versioned wire DTOs.

For `chunk_text` and `chunk_pdf`, section offsets are zero-based Python string
indices into `Document.text`: `[start_offset, end_offset)` selects that section's
own text, including its original heading. They are not UTF-8 byte offsets or PDF
coordinates, and do not include descendants. Inter-section separator whitespace
need not belong to either section. An empty root has the empty range `[0, 0)`.
Chunk text collapses whitespace and may group descendants or overlap in character
fallback; section offsets cannot be used as exact chunk occurrence anchors.
The lower-level `assemble_sections` expects normalized input; leading/trailing
whitespace is stripped internally and offsets refer to that stripped stream.

The empty-root range corrects an earlier pre-alpha defect where an empty root
claimed the entire document span. Root text, hierarchy and IDs are unchanged.

`semantic_hash` is SHA-256 of stripped text with whitespace collapsed to single
spaces. It is content-based and does not include profile, source or hierarchy.
The word semantic does not imply a model embedding or equivalence of legal meaning.

`chunk_id` is a 12-hex-character truncated SHA-256 prefixed with `chunk-`. Its input
includes source_name, section_id, global chunk order, method and a hash of profile
plus normalized text. Section IDs depend on source_name, path and repeated-path
occurrence. Renaming a source, moving a section or inserting earlier chunks can
change IDs while leaving content hashes unchanged. IDs are not globally unique
legal-unit identifiers or persistent citation locators. There is no structural_hash
field today.

Unique sibling reordering or inserting an earlier different path preserves a
section ID if its source, path and same-path occurrence are unchanged. It can
change chunk IDs through global order. A body-only edit preserves the section ID
but changes affected chunks' content hashes and IDs. Reparenting changes the path and
section ID. Identical repeated paths receive distinct occurrence IDs even when
content hashes are equal; inserting another occurrence can shift later identities.
Whitespace differences that collapse to identical chunk text leave content hashes
and chunk IDs unchanged when all their other identity inputs stay the same.
These scenarios are enforced in `tests/test_quality_contracts.py`; they are not a
promise of identity stability across engine versions.

Determinism applies with the same input, arguments, packaged assets and runtime.
It does not promise invariant output across extractor, asset or engine versions.

## Definition schedule text

Recognized definition entries retain their original quoted term, aliases and
operative wording in `Chunk.text`, with normal chunk whitespace collapse. The
parsed display term (for example `Notice / Notification`) remains metadata, not a
replacement for source text. Introduction, schedule heading and table heading
before the first entry are separate `statute_unit` chunks (character fallback
applies if needed). A schedule with no recognized entry follows ordinary grouping.
Definitions remain whole even if oversized; this preserves the existing semantic
unit behavior and is not a universal character limit.

This corrects earlier pre-alpha output that discarded the schedule introduction
and rewrote definitions as `term: definition`. Consumers must filter by method or
metadata rather than assume the first schedule chunk is a definition. Definition
text/content hashes and resulting chunk IDs change, and later global chunk orders
can shift. Document text and section hierarchy are unaffected by this correction.

## Trace coverage

`trace=True` adds matched-heading rejection and PDF text/page-removal decisions
with rule identities and reasons, alongside existing events. Result text/sections/
chunks are invariant to tracing. PDF event coordinates identify explicit source
planes and must not be treated as `Document.text` offsets. The additive events may
change event counts/order expectations and include discarded source text. See
[runtime decision traces](tracing.md) for fields, coverage and limitations.

## CLI serialization

`chunk` emits source/profile/language/policy plus full chunk records including text.
`structure` emits sections; `explain` emits trace; `review` emits human-readable
previews. Each command accepts text or a path, profile, doc-kind and output.

JSON uses dataclass conversion and `json.dumps(..., ensure_ascii=False, indent=2)`;
stdout and file output append a newline. This is not a canonical JSON standard or
versioned byte-level serialization contract. Python callers can use `asdict`, but
must choose their own serialization. Changes to results, IDs or trace need explicit
regression review and documentation; version bumps are release decisions.
