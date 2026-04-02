"""High-level library API."""

from __future__ import annotations

from pathlib import Path

from legal_chunking.detect.sections import assemble_sections
from legal_chunking.hashing import PIPELINE_VERSION, compute_semantic_hash
from legal_chunking.models import Chunk, Document, Section
from legal_chunking.normalize import normalize_chunk_text, normalize_extracted_text
from legal_chunking.profiles import resolve_profile


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


def _build_fallback_chunks(sections: list[Section]) -> list[Chunk]:
    chunks: list[Chunk] = []
    order = 1
    for section in sections:
        normalized_chunk = normalize_chunk_text(section.text)
        if not normalized_chunk:
            continue
        semantic_hash = compute_semantic_hash(normalized_chunk)
        chunks.append(
            Chunk(
                chunk_id=f"chunk-{semantic_hash[:12]}",
                text=normalized_chunk,
                order=order,
                section_id=section.section_id,
                section_title=section.title,
                article_number=section.article_number,
                paragraph_number=section.paragraph_number,
                semantic_hash=semantic_hash,
            )
        )
        order += 1
    return _assign_chunk_adjacency(chunks)


def chunk_text(text: str, profile: str = "generic", source_name: str = "<memory>") -> Document:
    """Return deterministic sections and fallback chunks for normalized text input."""
    resolved_profile = resolve_profile(profile)
    normalized_document = normalize_extracted_text(text)
    sections = assemble_sections(
        normalized_document,
        profile=resolved_profile.code,
        source_name=source_name,
    )
    chunks = _build_fallback_chunks(sections)
    return Document(
        source_name=source_name,
        profile=resolved_profile.code,
        language=resolved_profile.language,
        text=normalized_document,
        pipeline_version=PIPELINE_VERSION,
        sections=sections,
        chunks=chunks,
    )


def chunk_pdf(path: str | Path, profile: str = "generic") -> Document:
    """Read a PDF path placeholder until PDF extraction is implemented."""
    source = Path(path)
    resolved_profile = resolve_profile(profile)
    return Document(
        source_name=source.name,
        profile=resolved_profile.code,
        language=resolved_profile.language,
        text="",
        pipeline_version=PIPELINE_VERSION,
        chunks=[],
    )
