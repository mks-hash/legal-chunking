# Runtime decision traces

`chunk_text(..., trace=True)` and `chunk_pdf(..., trace=True)` attach a TraceReport.
CLI `explain` runs the same engine. Tracing observes actual decisions; it does not
run a second detector or reconstruct reasons from the final output. With identical
input/config/runtime, enabling trace leaves document text, sections, chunks,
metadata, offsets and IDs unchanged. Event order is deterministic runtime order,
not a regrouping by stage. This is pre-alpha, not a frozen event serialization schema.

## Heading decisions

During section assembly (or an explicitly traced internal detector call),
`heading_candidate_rejected` is emitted only when a profile pattern matched and
its candidate failed an admissibility or contextual check. It carries `rule_id`,
`reason`, `detector`, `text`, `offset`, `profile` and `chunk_policy`.
An ordinary unmatched body line is not presented as a rejected heading.

Rule IDs identify their owner and actual failed condition, for example:

- `heading.numeric.lowercase_title`: the candidate title starts in lowercase.
- `heading.numeric.missing_marker`: a number lacks the required heading marker.
- `heading.rule.weak_pronoun`: a rule title begins with a weak pronoun/article.
- `heading.article.parenthesized_title`: a citation-like parenthesized tail.
- `heading.roman_heading.signature_name`: signature-name shape in a profile
  that blocks it; the detector is the pattern that actually matched.
- `heading.article.guidance_policy`: article headings blocked by guidance policy.
- `heading.context.article_body_numeric`: an otherwise admissible numeric
  candidate cannot replace its containing statute article; `candidate_label`
  retains the proposed label.

Length, word count, punctuation, symbolic-marker and other existing admissibility
checks have corresponding reason IDs. The first failed check owns the reason;
it is not an exhaustive list of all possible objections to a candidate.
Some detectors continue to another pattern after rejection. A rejection therefore
can precede acceptance of an alternative interpretation of the same line.

`heading_detected` records the final accepted assembly heading, its label, kind,
offset and `rule_id="section.heading.accepted"`. In the high-level pipeline offsets
are Python character indices into processed `Document.text`. Prefix handling may
report a rejected sub-candidate at its substring offset. Direct internal detector
calls without a source offset report `offset=None`.

## PDF cleanup decisions

`pdf_text_removed` records discarded text and the rule that actually removed it.
`pdf_page_removed` records aggregate page exclusions. Both use extraction stage
and the original one-based `page_number` supplied by the adapter, when available.
Direct low-level page normalization without page metadata reports `None`.

| Rule | Observed decision |
| --- | --- |
| `pdf.line.profile_noise.<profile>` | Matching profile policy; `policy_field` and `policy_value` identify the actual equality/regex rule |
| `pdf.margin.repeated_leading` | Contiguous repeated leading fragments removed by margin trimming |
| `pdf.margin.repeated_trailing` | Contiguous repeated trailing fragments removed by margin trimming |
| `pdf.margin.us_running_rule` | Actual prefix removed by the US running-rule-header helper |
| Candidate `pdf.line.*` rule | Classified page-number/running-header/TOC line excluded, or a refined parser-state rejection |
| `pdf.page.toc_leader_cluster` | Page excluded because at least two TOC leaders have target pages; includes actual `toc_leader_count` |
| `pdf.document.us_rules_front_matter` | Cleaned pages preceding the selected US rules body |
| `pdf.document.us_rules_body_prefix` | Cleaned first-body-page prefix before the selected body marker |

Coordinates are explicitly tied to `input_stage`:

- **normalized_page_lines:** `line_number` is one-based in the extractor page
  stream after the adapter's existing CR-to-LF newline handling, before empty/profile
  lines or margins are removed. Numbers retain gaps and distinguish duplicate lines.
- **refined_page_lines:** `line_number` addresses the stream after marker and wrapped
  heading merges. It is not an original extractor line index.
- **cleaned_page_text:** page text after cleanup, before document-level front-matter
  trimming. A prefix event has `[start_offset, end_offset)` in that page text.

These are not offsets in `Document.text`, PDF coordinates, or end-to-end provenance
anchors. A TOC page event contains the remaining normalized lines at exclusion time;
a front-matter page event contains the cleaned page text. Earlier removals may have
separate events in their own source plane. Whitespace-only lines do not get removal
events. Kept body text is not labelled as removed merely because its spelling repeats.

## Coverage and handling

The trace now covers matched heading rejection during section assembly and the page/document exclusion
points listed above. It does not cover every normalization, dehyphenation, marker
merge, guidance candidate, title-only chunk preamble omission or definition parsing
choice. Existing classification/state and chunk-boundary events remain available.
Do not infer complete instrumentation from stage names or the presence of events.

Events contain source text, including material discarded from the final document.
Full-page events can expose more text than a chunk preview; enabling trace increases
memory/output size. Callers decide whether to retain/share traces. There is no
redaction or event-budget API today. Trace reasons explain the configured heuristic,
not its legal correctness; original-source review remains necessary.
