# Quality evidence and review

A passing test suite protects specific contracts. It does not establish complete
jurisdiction coverage, correct OCR or faithfulness to every original document.

## Public reviewed examples

[Quality fixtures](../tests/fixtures/quality/README.md) contain original synthetic
texts and independently authored expectations for generic, RU, US, EU and AE.
They exercise fitting statute units, chapter/part hierarchy, decimal numbering,
rule subdivisions, lettered sections and review approval/body separation.
`tests/test_quality_contracts.py` verifies exact own text, parents/paths, offsets,
chunk boundaries and ownership, adjacency and selected metadata.

Additional scenarios protect source renaming, earlier insertion, sibling reordering,
reparenting, identical repeated units, body edits, whitespace and empty input.
An oversized article test verifies that overlapping character fallback covers its
non-whitespace text and cannot consume the next article. Concatenating overlapping
chunks is not a general source-preservation check.

Fixtures are reviewed against their explicitly authored source, not certified
against applicable law. They are intentionally small. Definition schedules,
recitals, case-law forms, noisy extraction and references have existing focused
checks, but do not yet have equally complete independently reviewed fixtures in
this set. These are concrete expansion targets, not implied coverage.

## Three separate evidence levels

1. **Source expectations:** independently specified boundaries, hierarchy and text
   for small public examples. A mismatch requires investigation, not snapshot refresh.
2. **Processed-text invariants:** offsets select own text, ordered own-text spans
   preserve the processed stream, and IDs obey documented relationships. These
   checks cannot detect upstream deletion of original PDF content.
3. **Original-source fidelity:** inspect selected PDF pages and extracted results
   side by side, recording missing/added text, false boundaries and metadata errors.
   Counts and automated invariants alone do not satisfy this level.

## Local corpus review

Large PDFs, extracted source excerpts and review reports stay in ignored `.develop/`.
Record the source SHA-256, profile/doc-kind, backend/OCR configuration, Python and
extractor versions. Distinguish missing inputs from passes. Historical exports are
not goldens. If a defect can be represented by an original synthetic example,
protect it publicly without copying restricted source text.

For each inspected failure record the source location, expected boundary/text,
observed output, owning stage (extraction, normalization, assembly or chunking),
regression and resolution or outstanding status. Mark uninspected areas explicitly.
Compare against the original source before declaring a transformation harmless.

Use `python -m pytest -q tests/test_quality_contracts.py` for the public contracts;
`tests/test_real_pdfs.py` separately exercises optional local corpus integration.
See [development](development.md) for environment and skip reporting, and
[API contracts](api.md) for offsets and identity semantics.
