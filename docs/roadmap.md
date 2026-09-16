# Strategic roadmap

This is a sequence of outcomes, not a v1.1 release promise. The package is currently
pre-alpha (`0.1.0`). Legal Chunking's focus is extraction-agnostic, deterministic,
explainable document structuring; broader jurisdiction coverage follows engine
correctness and evidence, rather than driving ad hoc rules.

## Completed alpha improvements

The engine now shares marker-scoped numeric-script normalization, keeps fitting
statute primary units together, binds coordinated RU references, distinguishes review
body points from approval directives and emits a boundary event for every chunk.
PDF extraction has explicit native/layout backends and optional Tesseract OCR,
with isolated adapter execution and reproducibility metadata. Local corpus regression
coverage includes APK and the 2026 review. This is not schema freeze or a stable
release/readiness claim; full typed addresses, occurrence anchors and page provenance
still need concrete contracts.

## Quality-contract foundation

Independently authored public fixtures now protect own-text boundaries, hierarchy,
selected metadata and content preservation across all five enabled profiles.
Definitions, short/long recitals, case-law paragraph policy and noisy text/native
PDFs also have source expectations. Definition chunks preserve original wording
and schedule introduction; repetition cleanup is scoped to leading margin context.
Offset and relational identity scenarios have regressions; empty roots have empty
own-text spans. See [quality evidence](quality.md). This establishes a small
reviewed baseline, not complete source-PDF fidelity or completion of stages 1/2.

## 1. Establish trustworthy regression and quality evidence

Protect existing legal forms across all enabled profiles. Use the current local
PDF corpus to identify actual failures; derive small public text/synthetic PDF
regressions where redistribution is permitted. Record source provenance, extractor
version, arguments and observed differences. Golden expectations must be reviewed
against source text, not accepted automatically because the engine produced them.

Acceptance: representative fixtures assert boundaries, hierarchy, metadata, content
preservation and identity; local corpus failures are explained and corrected, and
missing optional fixtures are visibly distinguished from passing checks.

## 2. Define stable core contracts before a stable release

Specify normalization, section ownership/offsets, fallback behavior, identity and
API compatibility. Decide whether versioned serialization and provenance are
required before freezing a schema. Content hash and source-relative identity must
remain separate. Do not promise byte-identical output across engine versions.

Acceptance: documented contract changes have owning regressions; rename/reorder,
repeated-unit and whitespace scenarios have explicit expected behavior; installed
wheel and core-without-PDF checks pass. Only then choose a stable release number.

## 3. Improve explainability and extraction independence

Instrument important acceptance/rejection and boundary decisions with stable rule
identities, without duplicating the runtime in explain mode. Document trace coverage
and source-text exposure. Evaluate an extraction-neutral provenance/layout input
contract only against concrete use cases; avoid a plugin framework in advance.

Acceptance: a reviewer can explain selected difficult boundaries from runtime
facts; external extracted text uses the same core; extractor differences are
measured rather than hidden by a universal determinism claim.

## 4. Harden existing forms and performance

Prioritize source-backed defects in headings, guidance, rule subdivisions,
definitions and noisy input. Benchmark long and pathological documents with a
recorded environment; justify resource guards and make refusals observable.
Test re-entrancy/concurrency where shared caches or state materially affect results.

Acceptance: reviewed corpus regressions remain protected and measured runtime/memory
behavior supports the claimed input sizes. OCR and table recovery remain upstream
concerns unless a concrete structural contract warrants engine work.

## 5. Expand only on evidence

Add profiles or document families when reusable engine mechanics and licensed
fixtures justify them. Existing profiles must retain their regression behavior.
Optional terminal rendering is lower priority than faithful structure and traces.
Retrieval, embedding, routing taxonomies and product workflows remain downstream.
