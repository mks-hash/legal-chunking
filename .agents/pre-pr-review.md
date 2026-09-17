# Final review

Use before completing a substantial change or preparing a requested PR.

- Does the change preserve extraction independence and structure before chunking?
- Is the defect fixed at the existing owner, without duplicate policy or speculative
  deletion/reconstruction of legal text?
- Do public signatures, model fields, assets, docs and examples describe one behavior?
- Are source-relative IDs distinguished from content hashes? Have relevant rename,
  repeated-unit, order and normalization effects been considered?
- Are hierarchy, metadata, fallback and trace claims supported by meaningful tests?
- Could malformed input, noisy headings or optional-dependency failure corrupt
  output silently? Do diagnostics unnecessarily expose source text?
- Are real-PDF skips separated from passes, and source fidelity reviewed where needed?
- Are .develop files still ignored, and public instructions usable without them?
- Were the applicable pytest and Ruff checks run? State limitations honestly.
- Is the diff limited to the task? For a requested PR describe final behavior,
  validation and remaining risks; inspect actual GitHub rules before publishing.
