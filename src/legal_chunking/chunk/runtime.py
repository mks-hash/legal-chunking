"""Chunk assembly runtime orchestration."""

from __future__ import annotations

import hashlib

from legal_chunking.hashing import _compute_chunk_identity_hash, compute_semantic_hash
from legal_chunking.models import Chunk, LegalMetadata, LegalUnitType, Section
from legal_chunking.normalize import normalize_chunk_text
from legal_chunking.profiles import ChunkFallbackConfig, ResolvedProfile
from legal_chunking.tracing import TraceCollector

from .splitters import (
    ARTICLE_SPLITTERS,
    DOCUMENT_ROOT_SPLITTERS,
    OVERSIZED_SECTION_SPLITTERS,
    ChunkSplit,
    group_paragraphs,
    is_definition_schedule,
    split_definition_schedule,
    split_guidance_point,
    split_paragraph_units,
    split_paragraphs,
)


def build_chunks(
    sections: list[Section],
    *,
    source_name: str,
    resolved_profile: ResolvedProfile,
    chunk_policy: str,
    fallback: ChunkFallbackConfig,
    trace: TraceCollector | None = None,
) -> list[Chunk]:
    """Build deterministic chunks from parsed sections and one resolved policy."""
    selected_sections = select_sections(sections, chunk_policy=chunk_policy)
    chunks: list[Chunk] = []
    for section in selected_sections:
        parts = split_section(
            section,
            resolved_profile=resolved_profile,
            chunk_policy=chunk_policy,
            fallback=fallback,
            trace=trace,
        )
        for chunk_method, part, legal_unit_type, legal_unit_number, definition_term in parts:
            append_chunk(
                chunks,
                section=section,
                text=part,
                chunk_method=chunk_method,
                legal_unit_type=legal_unit_type,
                legal_unit_number=legal_unit_number,
                definition_term=definition_term,
                source_name=source_name,
                profile=resolved_profile.code,
            )
    return assign_chunk_adjacency(chunks)


def append_chunk(
    chunks: list[Chunk],
    *,
    section: Section,
    text: str,
    chunk_method: str,
    legal_unit_type: LegalUnitType | None,
    legal_unit_number: str | None,
    definition_term: str | None,
    source_name: str,
    profile: str,
) -> None:
    normalized_text = normalize_chunk_text(text)
    if not normalized_text:
        return

    order = len(chunks) + 1
    chunk_input_hash = _compute_chunk_identity_hash(text=normalized_text, profile=profile)
    raw = f"{source_name}:{section.section_id}:{order}:{chunk_method}:{chunk_input_hash}"
    chunk_id = f"chunk-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"
    chunks.append(
        Chunk(
            chunk_id=chunk_id,
            text=normalized_text,
            order=order,
            chunk_method=chunk_method,
            section_id=section.section_id,
            section_title=section.title,
            section_type=section.section_type or section.kind,
            metadata=LegalMetadata(
                article_number=section.metadata.article_number,
                paragraph_number=section.metadata.paragraph_number,
                point_number=section.metadata.point_number,
                legal_unit_type=legal_unit_type or section.metadata.legal_unit_type,
                legal_unit_number=legal_unit_number or section.metadata.legal_unit_number,
                source_case_reference=section.metadata.source_case_reference,
                source_case_number=section.metadata.source_case_number,
                source_case_date=section.metadata.source_case_date,
                source_case_court=section.metadata.source_case_court,
                definition_term=definition_term or section.metadata.definition_term,
            ),
            semantic_hash=compute_semantic_hash(normalized_text),
        )
    )


def assign_chunk_adjacency(chunks: list[Chunk]) -> list[Chunk]:
    for idx, chunk in enumerate(chunks):
        chunk.prev_chunk_id = chunks[idx - 1].chunk_id if idx > 0 else None
        chunk.next_chunk_id = chunks[idx + 1].chunk_id if idx + 1 < len(chunks) else None
    return chunks


def select_sections(sections: list[Section], *, chunk_policy: str) -> list[Section]:
    _ = chunk_policy
    return [section for section in sections if (section.text or "").strip()]


def split_section(
    section: Section,
    *,
    resolved_profile: ResolvedProfile,
    chunk_policy: str,
    fallback: ChunkFallbackConfig,
    trace: TraceCollector | None = None,
) -> list[ChunkSplit]:
    normalized = (section.text or "").strip()
    if not normalized:
        return []

    paragraphs = split_paragraphs(normalized)
    if chunk_policy == "guidance":
        is_guidance_point = (
            section.metadata.legal_unit_type == LegalUnitType.GUIDANCE_POINT
            or (section.section_type or "") == "review_point"
        )
        if is_guidance_point:
            if len(normalized) <= fallback.max_chars:
                return [("guidance_point", normalized, None, None, None)]
            return split_guidance_point(normalized, paragraphs, fallback)
        if section.kind == "document_root":
            return split_paragraph_units(paragraphs, fallback, base_method="guidance_preamble")
        return split_paragraph_units(paragraphs, fallback, base_method="guidance_block")

    if chunk_policy == "case_law":
        return split_paragraph_units(paragraphs, fallback, base_method="case_law_paragraph")

    if chunk_policy == "statute":
        runtime = resolved_profile.runtime.chunk
        document_root_splitter = DOCUMENT_ROOT_SPLITTERS.get(runtime.document_root_splitter)
        if section.kind == "document_root" and document_root_splitter is not None:
            return document_root_splitter(section.text, fallback)
        if is_definition_schedule(section):
            definition_chunks = split_definition_schedule(section, trace=trace)
            if definition_chunks:
                return definition_chunks
        article_splitter = ARTICLE_SPLITTERS.get(runtime.article_splitter)
        if (section.section_type or "") == "article" and article_splitter is not None:
            article_chunks = article_splitter(section, fallback, trace=trace)
            if article_chunks:
                return article_chunks
        section_splitter = OVERSIZED_SECTION_SPLITTERS.get(runtime.oversized_section_splitter)
        if (
            section_splitter is not None
            and (section.section_type or "") == "section"
            and len(normalized) > fallback.max_chars
        ):
            oversized_chunks = section_splitter(section, trace=trace)
            if oversized_chunks:
                return oversized_chunks
        return group_paragraphs(paragraphs, fallback, base_method="statute_unit")

    return group_paragraphs(paragraphs, fallback, base_method="by_section")


__all__ = [
    "append_chunk",
    "assign_chunk_adjacency",
    "build_chunks",
    "select_sections",
    "split_section",
]
