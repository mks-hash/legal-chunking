# Architecture: Structural Legal Chunking

`legal-chunking` is a deterministic, structure-first parser and chunking engine. Unlike generic text splitters that rely on character windows or shallow heuristics, this library reconstructs the semantic hierarchy of legal documents before deciding where to split.

## The Cognitive Pipeline

The processing follows a strict linear sequence:

1.  **Extract**: Binary PDF or text ingestion into a raw line stream with layout metadata.
2.  **Normalize**: Deterministic cleaning of noise (headers/footers) and standardization of characters.
3.  **Detect**: Structural marker identification (Articles, Sections, Rules, Recitals) using jurisdiction-specific assets.
4.  **Assemble**: Reconstruction of the document tree (e.g., nesting Rule 4 -> Section (a) -> Point (1)).
5.  **Chunk**: Splitting the document at logical legal boundaries defined by the Chunking Policy.
6.  **Trace**: Generation of an explainable trace for every architectural decision.

## Design Invariants

- **Deterministic**: Identical inputs always produce identical chunk IDs and content hashes.
- **Structure-First**: Chunking is a downstream effect of structural understanding, not a separate process.
- **Dependency-Light**: Built with modern Python and minimal external dependencies for portability.
- **Explainable**: The internal "thinking process" of the parser is exposed via the CLI `explain` command.
