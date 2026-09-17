# Reference occurrences and source anchors

Reference analysis identifies citation components and local document-family context.
It does not resolve authoritative documents, editions or legal validity.

## Two result contracts

`extract_references(text, *, profile="generic", doc_family=None)` retains its
existing list of ParsedReference objects. It deduplicates component keys globally
and preserves existing pattern traversal order and first retained normalized `raw`.
It is useful when occurrences and original-text highlighting are unnecessary.

`analyze_references(text, *, profile="generic", doc_family=None)` returns a frozen
ReferenceAnalysis with resolved `profile`, `normalized_text` and an ordered tuple
of ReferenceOccurrence objects. It uses the same normalization, patterns, family
restrictions and scoped-container admission as extraction. The additional projection
retains repeated source occurrences and prefers the longest overlapping spelling
of the same component. It does not run a separate parser or match repaired values
back to the input with substring search/fuzzy alignment.

```python
from legal_chunking import analyze_references

source = "статья 2295 АПК РФ; статья 229⁵ АПК РФ"
analysis = analyze_references(source, profile="ru")

for occurrence in analysis.occurrences:
    assert source[occurrence.start_offset:occurrence.end_offset] == occurrence.raw
    print(occurrence.raw)  # статья 2295, then статья 229⁵
    print(occurrence.references[0].article_number)  # 229.5 in both cases
```

## Coordinates and grouped components

Each occurrence contains:

| Field | Meaning |
| --- | --- |
| `start_offset`, `end_offset` | Zero-based Python string indices in the exact supplied input; half-open range |
| `raw` | Verbatim input slice of that range |
| `normalized_start_offset`, `normalized_end_offset` | Half-open range in `analysis.normalized_text` |
| `references` | Tuple of ParsedReference components associated with that selected locator match |

Every component's `ParsedReference.raw` is its selected normalized-view match.
It is deliberately distinct from `occurrence.raw`. Python offsets count Unicode
characters, not UTF-8 bytes or JavaScript UTF-16 code units. They are snapshot
positions, not persistent citation identifiers.

`части 3, 4 статьи 65 АПК РФ` has one locator occurrence containing two references
(article 65 / part 3, article 65 / part 4). Repeating the phrase creates another
occurrence with its own input interval. Duplicate list members remain represented
inside the occurrence; legacy extraction still deduplicates them. Existing
Cartesian list-composition semantics are unchanged, and ranges remain strings
without invented expansion.

Occurrences are in normalized source order. Identical generic alternatives at the
same interval/component are coalesced. Overlapping alternatives of the same
component prefer the longest match (for example a full U.S.C. spelling over its
nested section-marker spelling). Distinct components can still have overlapping
intervals. The legacy list retains its previous ordering/raw choices; do not expect
raw-object equality with a global deduplication of the source-ordered analysis.

The matched locator may exclude a source alias such as `ГК РФ`; local family context
can be resolved outside its interval. These spans are not guaranteed to cover the
entire bibliographic citation or provide individual subranges for each list member.

## Normalization provenance

The actual normalization edits optionally carry source intervals. Equal replacement
edges keep exact character origins; the changed middle has a covering input interval.
Inserted punctuation is anchored to its source boundary. This supports superscripts,
approved merged/split numbering, whitespace/control cleanup and existing contextual
repairs even when the same normalized value appears several times.

An occurrence is a contiguous covering span of its surviving matched content.
Deleted artifacts inside its boundaries remain present in its verbatim `raw`;
deleted trailing artifacts can fall outside the span. For example citation repair
of `статья 443[1]` yields the locator slice `статья 443`. There is no public per-glyph
edit map, bounding box or legal-unit provenance graph.

When passing `Document.text`, input coordinates address that canonical document
plane. When passing externally extracted text, they address that external string.
Neither recovers upstream discarded content or original PDF coordinates.

Source mapping is opt-in to analysis. Legacy normalization/extraction does not
allocate per-character origin buffers. Maps are local to the call and not cached;
analysis uses input-size-dependent memory and returns normalized text plus verbatim
locator snippets. No public resource budget or complete performance guarantee exists.
Use `dataclasses.asdict` for payloads; these are pre-alpha dataclasses, not a frozen
versioned wire schema.

## Compatibility correction

Context checks for remaining superscripts now read the current replacement input
view after structural numbering normalization. Previously the first replacement
could shift the second endpoint, leaving `статьи 225¹⁶⁻¹–225¹⁶⁻³ АПК РФ` partially
normalized. Both ends now normalize to `225.16-1–225.16-3`; the existing extractor
therefore returns the full range instead of the truncated first identifier.
This is a documented bug fix, separate from the additive occurrence API. Legacy
signatures, deduplication, scopes and ordering are retained.

The legacy `paragraph_number` slot for RU points and `article_number` slot for
chapters remain unchanged. Full typed locator chains, ordinal-paragraph/subpoint
roles, authoritative target resolution and PDF provenance remain roadmap work.
