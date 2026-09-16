---
name: legal-engine
description: Change or review Legal Chunking structure, normalization, profiles, references, identity or trace contracts and their documentation.
---

# Legal engine changes

Read root AGENTS.md and the relevant docs/architecture.md or docs/api.md contract.

Locate the existing owner before editing:

- Composition: src/legal_chunking/api.py.
- Profile vocabulary/defaults: packaged assets via manifest.py/profiles.py.
- Runtime policy: runtime_policy.py and assets/chunking_policy/.
- PDF-specific candidates, context and cleanup: extract/pdf*.
- Heading admissibility and section assembly: detect/heading* and detect/section*.
- Specialized forms: detect/guidance*, definitions.py and rulebook.py.
- Splitting and IDs: chunk/runtime.py, chunk/splitters.py and hashing.py.
- References: reference_parser.py, references.py and reference_context.py.

Preserve text/PDF independence. A PDF cleanup defect belongs to the adapter;
a structural defect reproducible from text belongs to the core. Avoid fixing lost
extraction data with downstream speculative text reconstruction.

For pattern changes distinguish local detection from contextual admissibility and
final assembly. Extend an existing asset/policy or narrowly scoped detector; do
not force generic normalization to delete a jurisdiction-specific legal form.
Test both the intended match and plausible legal text that must remain intact.

For chunk changes inspect section ownership, legal metadata and fallback method,
including oversized guidance points that intentionally stay whole. For identity
changes review source rename, order/path changes and repeated units separately
from whitespace-stable content hashing. There is no structural_hash today.

Trace comes from the same runtime. Check event meaning and source-text exposure;
do not claim complete instrumentation or change events solely to satisfy a snapshot.

Use owning tests listed in docs/development.md and existing fixtures first. Run the
full suite for structural/normalization/policy/identity changes. Real PDFs are
optional local fixtures in .develop/testings; report skips and manually inspect
source fidelity when a change affects noisy extraction or difficult boundaries.
Do not move the large corpus into public tests.

Update the owning docs when behavior changes. Future design belongs in
 docs/roadmap.md, with acceptance criteria rather than an unsupported release claim.
