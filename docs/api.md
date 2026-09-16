# API and result contracts

The package version is `0.1.0` in `pyproject.toml`; this is pre-alpha. The current
API and serialization are documented behavior, not a frozen v1 schema.

## Public package exports

`legal_chunking.__all__` exports:

- `chunk_text`, `chunk_pdf`, `assemble_sections`, `extract_references`;
- `Document`, `Section`, `Chunk`, `ParsedReference`;
- `LegalChunkingError`, `AssetConfigError`, `InvalidProfileError`,
  `PdfDependencyError`.

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
trace=False)` returns the same model and uses the file basename as source_name.

`assemble_sections(text, *, profile="generic", chunk_policy="default",
doc_kind=None, source_name="<memory>", trace=None)` returns sections. This lower
level API expects normalized text and an explicit policy; it does not perform the
high-level API's normalization/policy selection. Its trace parameter is an internal
collector, not the high-level boolean.

`extract_references(text, *, profile="generic", doc_family=None)` returns ParsedReference objects.
An explicit doc_family narrows family-scoped matching. Reference normalization is
separate from document normalization. `raw` reflects
the parser's normalized matching text, not guaranteed verbatim source bytes.
References identify citation components and optional document family; they do not
resolve a citation to an authoritative document, edition or legal validity.
Use `to_dict()` or `to_canonical_parts(jurisdiction=...)` for reference payloads.

Profile codes or aliases resolve through the manifest. Unknown/disabled profiles
raise InvalidProfileError. Unknown doc_kind values currently select the asset's
`other` policy, then `code`, rather than raising a validation error. Missing PDF
support raises PdfDependencyError; asset failures use AssetConfigError. Ordinary
IO and some configuration errors may still be standard Python exceptions.

## Results and identity

Document contains source_name, resolved profile, language, normalized text,
chunk_policy, sections, chunks and optional trace. Section contains hierarchy,
metadata, processed-text offsets and text. Chunk contains text, method, section
association, legal metadata, semantic_hash and previous/next chunk IDs.
The models are dataclasses; they are not frozen schema/versioned wire DTOs.

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

Determinism applies with the same input, arguments, packaged assets and runtime.
It does not promise invariant output across extractor, asset or engine versions.

## CLI serialization

`chunk` emits source/profile/language/policy plus full chunk records including text.
`structure` emits sections; `explain` emits trace; `review` emits human-readable
previews. Each command accepts text or a path, profile, doc-kind and output.

JSON uses dataclass conversion and `json.dumps(..., ensure_ascii=False, indent=2)`;
stdout and file output append a newline. This is not a canonical JSON standard or
versioned byte-level serialization contract. Python callers can use `asdict`, but
must choose their own serialization. Changes to results, IDs or trace need explicit
regression review and documentation; version bumps are release decisions.
