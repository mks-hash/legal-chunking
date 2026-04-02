"""High-level library API."""

from __future__ import annotations

from pathlib import Path

from legal_chunking.hashing import PIPELINE_VERSION, compute_semantic_hash
from legal_chunking.models import Chunk, Document
from legal_chunking.normalize import normalize_chunk_text, normalize_extracted_text


def _assign_chunk_adjacency(chunks: list[Chunk]) -> list[Chunk]:
    """Assign previous and next chunk identifiers from stable final order."""
    if not chunks:
        return chunks

    ordered = sorted(enumerate(chunks), key=lambda item: (item[1].order, item[0]))
    for idx, (_original_idx, chunk) in enumerate(ordered):
        prev_chunk = ordered[idx - 1][1] if idx > 0 else None
        next_chunk = ordered[idx + 1][1] if idx + 1 < len(ordered) else None
        chunk.prev_chunk_id = prev_chunk.chunk_id if prev_chunk else None
        chunk.next_chunk_id = next_chunk.chunk_id if next_chunk else None

    return chunks


def chunk_text(text: str, profile: str = "generic", source_name: str = "<memory>") -> Document:
    """Return one deterministic normalized chunk until structure parsing lands."""
    normalized_document = normalize_extracted_text(text)
    normalized_chunk = normalize_chunk_text(normalized_document)
    semantic_hash = compute_semantic_hash(normalized_chunk)
    chunk = Chunk(
        chunk_id=f"chunk-{semantic_hash[:12]}",
        text=normalized_chunk,
        order=1,
        semantic_hash=semantic_hash,
    )
    _assign_chunk_adjacency([chunk])
    return Document(
        source_name=source_name,
        profile=profile,
        language=None,
        text=normalized_document,
        pipeline_version=PIPELINE_VERSION,
        chunks=[chunk] if normalized_chunk else [],
    )


def chunk_pdf(path: str | Path, profile: str = "generic") -> Document:
    """Read a PDF path placeholder until PDF extraction is implemented."""
    source = Path(path)
    return Document(
        source_name=source.name,
        profile=profile,
        language=None,
        text="",
        pipeline_version=PIPELINE_VERSION,
        chunks=[],
    )
