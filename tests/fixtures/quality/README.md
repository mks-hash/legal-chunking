# Reviewed quality fixtures

These eleven fixtures are original synthetic texts written for this repository,
covered by its Apache-2.0 license. They are not quotations from statutes or
representations of current law. Numbering and forms illustrate engine contracts.

Each JSON file pairs source text with explicitly authored expected own-text
sections, parent indices, chunk boundaries/methods and selected legal metadata.
The expectations were written before running the engine, then checked against
those source texts. They are not generated snapshots. Source-relative IDs are
checked relationally in tests rather than frozen as version-independent hashes.

| Fixture | Source-backed expectation |
| --- | --- |
| `generic` | Two explicit sibling articles; empty root |
| `ru_compound_article` | Raised multi-digit suffix with internal hyphen; exact article/chunk number |
| `ru_statute` | Decimal chapter/article identifiers; body points stay in article |
| `ru_guidance` | Approval directives stay in preamble; body points 1 and 2 |
| `eu_statute` | Chapter ownership; numbered paragraphs stay with article |
| `us_rule` | Rule ownership; letter/number subdivisions remain in rule |
| `ae_rulebook` | Lettered sections under part; original heading text preserved |
| `ae_definitions` | Schedule introduction and original quoted definitions; aliases in metadata |
| `eu_recitals` | Numbered recitals remain preamble, separate from operative article |
| `generic_case_law` | Three paragraph units under case-law policy; no invented hierarchy |
| `generic_noisy_text` | CRLF/NBSP/NUL cleanup with declared canonical text; spaced hyphen preserved |

The tests assert exact source preservation for these short fitting units, full
hierarchy, offsets, chunk ownership/adjacency and specified metadata. They do not
assert exhaustive jurisdiction support, OCR accuracy or source PDF fidelity.

To extend: write a small redistributable source, mark intended legal boundaries
and parents by inspecting that source, and author expectations before executing
the engine. Investigate failures against the source; never refresh expectations
from actual output automatically. Existing fixtures outside this directory retain
their narrower historical test roles.

`input_text`, when present, is the noisy input; `text` is the independently declared
processed source plane. Synthetic PDF tests construct native pages at runtime and
check repeated header cleanup while retaining identical operative body sentences.
Long recital tests check subdivision grouping beyond the configured budget.
