"""Policy-aware chunk assembly over parsed legal sections."""

from __future__ import annotations

import hashlib
import re

from legal_chunking.detect.definitions import parse_definition_entries
from legal_chunking.detect.rulebook import split_rulebook_rule_blocks
from legal_chunking.hashing import _compute_chunk_identity_hash, compute_semantic_hash
from legal_chunking.models import Chunk, Section
from legal_chunking.normalize import normalize_chunk_text
from legal_chunking.profiles import ChunkFallbackConfig
from legal_chunking.tracing import TraceCollector


def build_chunks(
    sections: list[Section],
    *,
    source_name: str,
    profile: str,
    chunk_policy: str,
    fallback: ChunkFallbackConfig,
    trace: TraceCollector | None = None,
) -> list[Chunk]:
    """Build deterministic chunks from parsed sections and one resolved policy."""
    selected_sections = _select_sections(sections, chunk_policy=chunk_policy)
    chunks: list[Chunk] = []
    for section in selected_sections:
        parts = _split_section(
            section,
            profile=profile,
            chunk_policy=chunk_policy,
            fallback=fallback,
            trace=trace,
        )
        for (
            chunk_method,
            part,
            legal_unit_type,
            legal_unit_number,
            definition_term,
        ) in parts:
            _append_chunk(
                chunks,
                section=section,
                text=part,
                chunk_method=chunk_method,
                legal_unit_type=legal_unit_type,
                legal_unit_number=legal_unit_number,
                definition_term=definition_term,
                source_name=source_name,
                profile=profile,
            )
    return _assign_chunk_adjacency(chunks)


def _append_chunk(
    chunks: list[Chunk],
    *,
    section: Section,
    text: str,
    chunk_method: str,
    legal_unit_type: str | None,
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
            article_number=section.article_number,
            paragraph_number=section.paragraph_number,
            point_number=section.point_number,
            legal_unit_type=legal_unit_type or section.legal_unit_type,
            legal_unit_number=legal_unit_number or section.legal_unit_number,
            source_case_reference=section.source_case_reference,
            source_case_number=section.source_case_number,
            source_case_date=section.source_case_date,
            source_case_court=section.source_case_court,
            definition_term=definition_term or section.definition_term,
            semantic_hash=compute_semantic_hash(normalized_text),
        )
    )


def _assign_chunk_adjacency(chunks: list[Chunk]) -> list[Chunk]:
    for idx, chunk in enumerate(chunks):
        chunk.prev_chunk_id = chunks[idx - 1].chunk_id if idx > 0 else None
        chunk.next_chunk_id = chunks[idx + 1].chunk_id if idx + 1 < len(chunks) else None
    return chunks


def _select_sections(sections: list[Section], *, chunk_policy: str) -> list[Section]:
    _ = chunk_policy
    return [section for section in sections if (section.text or "").strip()]


def _split_section(
    section: Section,
    *,
    profile: str,
    chunk_policy: str,
    fallback: ChunkFallbackConfig,
    trace: TraceCollector | None = None,
) -> list[tuple[str, str, str | None, str | None, str | None]]:
    normalized = (section.text or "").strip()
    if not normalized:
        return []

    paragraphs = _split_paragraphs(normalized)
    if chunk_policy == "guidance":
        is_guidance_point = (
            (section.legal_unit_type or "") == "guidance_point"
            or (section.section_type or "") == "review_point"
        )
        if is_guidance_point:
            if len(normalized) <= fallback.max_chars:
                return [("guidance_point", normalized, None, None, None)]
            return _split_guidance_point(normalized, paragraphs, fallback)
        if section.kind == "document_root":
            return _split_paragraph_units(paragraphs, fallback, base_method="guidance_preamble")
        return _split_paragraph_units(paragraphs, fallback, base_method="guidance_block")
    if chunk_policy == "case_law":
        return _split_paragraph_units(paragraphs, fallback, base_method="case_law_paragraph")
    if chunk_policy == "statute":
        if _is_definition_schedule(section):
            definition_chunks = _split_definition_schedule(section, trace=trace)
            if definition_chunks:
                return definition_chunks
        if (
            profile == "ae"
            and (section.section_type or "") == "section"
            and len(normalized) > fallback.max_chars
        ):
            rule_chunks = _split_rulebook_section(section, trace=trace)
            if rule_chunks:
                return rule_chunks
        return _group_paragraphs(paragraphs, fallback, base_method="statute_unit")
    return _group_paragraphs(paragraphs, fallback, base_method="by_section")


def _split_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    return parts if parts else [text.strip()]


def _group_paragraphs(
    paragraphs: list[str],
    fallback: ChunkFallbackConfig,
    *,
    base_method: str,
) -> list[tuple[str, str, str | None, str | None, str | None]]:
    chunks: list[tuple[str, str, str | None, str | None, str | None]] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if buffer:
            chunks.append((base_method, "\n\n".join(buffer).strip(), None, None, None))
            buffer.clear()

    for paragraph in paragraphs:
        if len(paragraph) > fallback.max_chars:
            flush_buffer()
            chunks.extend(_split_by_chars(paragraph, fallback))
            continue

        candidate_parts = [*buffer, paragraph]
        candidate = "\n\n".join(candidate_parts).strip()
        if candidate and len(candidate) <= fallback.max_chars:
            buffer = candidate_parts
            continue

        flush_buffer()
        buffer.append(paragraph)

    flush_buffer()
    return chunks


def _split_paragraph_units(
    paragraphs: list[str],
    fallback: ChunkFallbackConfig,
    *,
    base_method: str,
) -> list[tuple[str, str, str | None, str | None, str | None]]:
    chunks: list[tuple[str, str, str | None, str | None, str | None]] = []
    for paragraph in paragraphs:
        if len(paragraph) > fallback.max_chars:
            chunks.extend(_split_by_chars(paragraph, fallback))
            continue
        chunks.append((base_method, paragraph, None, None, None))
    return chunks


def _split_guidance_point(
    text: str,
    paragraphs: list[str],
    fallback: ChunkFallbackConfig,
) -> list[tuple[str, str, str | None, str | None, str | None]]:
    _ = paragraphs
    _ = fallback
    return [("guidance_point", text, None, None, None)]


def _split_by_chars(
    text: str,
    fallback: ChunkFallbackConfig,
) -> list[tuple[str, str, str | None, str | None, str | None]]:
    chunks: list[tuple[str, str, str | None, str | None, str | None]] = []
    start = 0
    step = fallback.max_chars - fallback.overlap_chars
    while start < len(text):
        end = min(len(text), start + fallback.max_chars)
        part = text[start:end].strip()
        if part:
            chunks.append(("char_fallback", part, None, None, None))
        if end >= len(text):
            break
        start += step
    return chunks


def _split_rulebook_section(
    section: Section,
    *,
    trace: TraceCollector | None = None,
) -> list[tuple[str, str, str | None, str | None, str | None]]:
    blocks = split_rulebook_rule_blocks(section.text)
    if not blocks:
        return []
    if trace is not None:
        trace.emit(
            "rule_block_split",
            section=section.title,
            count=len(blocks),
        )
    parts: list[tuple[str, str, str | None, str | None, str | None]] = []
    for block in blocks:
        block_text = f"{section.title}\n{block.number}. {block.text}".strip()
        parts.append(("statute_rule", block_text, "rule_block", block.number, None))
    return parts


def _is_definition_schedule(section: Section) -> bool:
    title = (section.title or "").strip().lower()
    return (section.section_type or "") == "other" and "definition" in title


def _split_definition_schedule(
    section: Section,
    *,
    trace: TraceCollector | None = None,
) -> list[tuple[str, str, str | None, str | None, str | None]]:
    entries = parse_definition_entries(section.text)
    if not entries:
        return []
    if trace is not None:
        trace.emit(
            "definition_schedule_split",
            section=section.title,
            count=len(entries),
        )
    parts: list[tuple[str, str, str | None, str | None, str | None]] = []
    for entry in entries:
        entry_text = f"{entry.term}: {entry.definition}".strip()
        parts.append(
            (
                "definition_entry",
                entry_text,
                "definition_entry",
                entry.term,
                entry.term,
            )
        )
    return parts
