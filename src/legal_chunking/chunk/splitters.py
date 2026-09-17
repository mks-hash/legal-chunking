"""Chunk splitter primitives and profile-scoped splitter implementations."""

from __future__ import annotations

import re
from typing import Protocol

from legal_chunking.detect.definitions import _parse_definition_spans
from legal_chunking.detect.rulebook import split_rulebook_rule_blocks
from legal_chunking.errors import AssetConfigError
from legal_chunking.models import LegalUnitType, Section
from legal_chunking.profiles import ChunkFallbackConfig
from legal_chunking.tracing import TraceCollector, TraceStage

ChunkSplit = tuple[str, str, LegalUnitType | None, str | None, str | None]


class DocumentRootSplitter(Protocol):
    def __call__(
        self, text: str, fallback: ChunkFallbackConfig, *, pattern: re.Pattern[str] | None = None
    ) -> list[ChunkSplit]: ...


class ArticleSplitter(Protocol):
    def __call__(
        self,
        section: Section,
        fallback: ChunkFallbackConfig,
        *,
        pattern: re.Pattern[str],
        trace: TraceCollector | None = None,
    ) -> list[ChunkSplit]: ...


class OversizedSectionSplitter(Protocol):
    def __call__(
        self, section: Section, *, trace: TraceCollector | None = None
    ) -> list[ChunkSplit]: ...


def split_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    return parts if parts else [text.strip()]


def group_paragraphs(
    paragraphs: list[str],
    fallback: ChunkFallbackConfig,
    *,
    base_method: str,
) -> list[ChunkSplit]:
    chunks: list[ChunkSplit] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if buffer:
            chunks.append((base_method, "\n\n".join(buffer).strip(), None, None, None))
            buffer.clear()

    for paragraph in paragraphs:
        if len(paragraph) > fallback.max_chars:
            flush_buffer()
            chunks.extend(split_by_chars(paragraph, fallback))
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


def split_paragraph_units(
    paragraphs: list[str],
    fallback: ChunkFallbackConfig,
    *,
    base_method: str,
) -> list[ChunkSplit]:
    chunks: list[ChunkSplit] = []
    for paragraph in paragraphs:
        if len(paragraph) > fallback.max_chars:
            chunks.extend(split_by_chars(paragraph, fallback))
            continue
        chunks.append((base_method, paragraph, None, None, None))
    return chunks


def split_guidance_point(
    text: str,
    paragraphs: list[str],
    fallback: ChunkFallbackConfig,
) -> list[ChunkSplit]:
    _ = paragraphs
    _ = fallback
    return [("guidance_point", text, None, None, None)]


def split_by_chars(text: str, fallback: ChunkFallbackConfig) -> list[ChunkSplit]:
    chunks: list[ChunkSplit] = []
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


def split_ae_statute_preamble(
    text: str, fallback: ChunkFallbackConfig, *, pattern: re.Pattern[str] | None = None
) -> list[ChunkSplit]:
    paragraphs = split_paragraphs(text)
    cleaned_paragraphs = _drop_title_only_preamble(paragraphs)
    chunks: list[ChunkSplit] = []
    for paragraph in cleaned_paragraphs:
        if len(paragraph) <= fallback.max_chars:
            chunks.append(("statute_unit", paragraph, None, None, None))
            continue

        semantic_parts = _split_ae_intro_semantically(paragraph, fallback)
        if semantic_parts:
            chunks.extend(("statute_unit", part, None, None, None) for part in semantic_parts)
            continue

        chunks.extend(split_by_chars(paragraph, fallback))
    return chunks


def split_rulebook_section(
    section: Section,
    *,
    trace: TraceCollector | None = None,
) -> list[ChunkSplit]:
    blocks = split_rulebook_rule_blocks(section.text)
    if not blocks:
        return []
    if trace is not None:
        trace.emit(
            TraceStage.CHUNK,
            "rule_block_split",
            section=section.title,
            count=len(blocks),
        )
    return [
        (
            "statute_rule",
            f"{section.title}\n{block.number}. {block.text}".strip(),
            LegalUnitType.RULE_BLOCK,
            block.number,
            None,
        )
        for block in blocks
    ]


def split_article_section(
    section: Section,
    fallback: ChunkFallbackConfig,
    *,
    pattern: re.Pattern[str],
    trace: TraceCollector | None = None,
) -> list[ChunkSplit]:
    text = (section.text or "").strip()
    if len(text) <= fallback.max_chars:
        return []
    subdivisions = _split_subdivisions(text, pattern)
    if len(subdivisions) < 2:
        return []

    grouped = _group_text_units(subdivisions, max_chars=fallback.max_chars)
    if len(grouped) < 2:
        return []

    if trace is not None:
        trace.emit(
            TraceStage.CHUNK,
            "article_subdivision_split",
            section=section.title,
            count=len(grouped),
        )
    return [("statute_unit", part, None, None, None) for part in grouped]


def is_definition_schedule(section: Section) -> bool:
    title = (section.title or "").strip().lower()
    return (section.section_type or "") == "other" and "definition" in title


def split_definition_schedule(
    section: Section,
    fallback: ChunkFallbackConfig,
    *,
    trace: TraceCollector | None = None,
) -> list[ChunkSplit]:
    spans = _parse_definition_spans(section.text)
    if not spans:
        return []
    if trace is not None:
        trace.emit(
            TraceStage.CHUNK,
            "definition_schedule_split",
            section=section.title,
            count=len(spans),
        )
    chunks: list[ChunkSplit] = []
    preamble = section.text[: spans[0].start].strip()
    if preamble:
        chunks.extend(
            group_paragraphs(split_paragraphs(preamble), fallback, base_method="statute_unit")
        )
    for span in spans:
        chunks.append(
            (
                "definition_entry",
                section.text[span.start : span.end],
                LegalUnitType.DEFINITION_ENTRY,
                span.entry.term,
                span.entry.term,
            )
        )
    return chunks


def split_eu_recitals(
    text: str, fallback: ChunkFallbackConfig, *, pattern: re.Pattern[str] | None = None
) -> list[ChunkSplit]:
    if pattern is None:
        raise AssetConfigError("Recital splitter requires a subdivision pattern")
    text = (text or "").strip()
    if len(text) <= fallback.max_chars:
        return []
    subdivisions = _split_subdivisions(text, pattern)
    if len(subdivisions) < 2:
        return []

    grouped = _group_text_units(subdivisions, max_chars=fallback.max_chars)
    if len(grouped) < 2:
        return []

    return [("statute_unit", part, None, None, None) for part in grouped]


DOCUMENT_ROOT_SPLITTERS: dict[str, DocumentRootSplitter] = {
    "title_preamble": split_ae_statute_preamble,
    "eu_recitals": split_eu_recitals,
}

ARTICLE_SPLITTERS: dict[str, ArticleSplitter] = {
    "numbered_subdivisions": split_article_section,
}

OVERSIZED_SECTION_SPLITTERS: dict[str, OversizedSectionSplitter] = {
    "rulebook_numeric": split_rulebook_section,
}


def _drop_title_only_preamble(paragraphs: list[str]) -> list[str]:
    if len(paragraphs) < 2:
        return paragraphs
    first = paragraphs[0].strip()
    if not _looks_like_title_only_preamble(first):
        return paragraphs
    return paragraphs[1:]


def _looks_like_title_only_preamble(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    if "\n" in normalized:
        return False
    if len(normalized) > 120:
        return False
    if any(mark in normalized for mark in ".!?;:"):
        return False
    words = normalized.split()
    if not 3 <= len(words) <= 12:
        return False
    if "rulebook" in normalized.lower():
        return True
    letters = [char for char in normalized if char.isalpha()]
    if not letters:
        return False
    uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    if uppercase_ratio >= 0.55:
        return True
    title_like_words = sum(
        1 for word in words if word[:1].isupper() or any(char.isdigit() for char in word)
    )
    return title_like_words / len(words) >= 0.8


def _split_ae_intro_semantically(text: str, fallback: ChunkFallbackConfig) -> list[str]:
    parts = _split_bullet_paragraph(text)
    if len(parts) >= 2 and all(len(part) <= fallback.max_chars for part in parts):
        return parts

    sentences = _split_sentence_like_units(text)
    grouped = _group_text_units(sentences, max_chars=fallback.max_chars)
    if len(grouped) >= 2 and all(len(part) <= fallback.max_chars for part in grouped):
        return grouped
    return []


def _split_bullet_paragraph(text: str) -> list[str]:
    normalized = (text or "").strip()
    if "•" not in normalized:
        return []
    raw_parts = [part.strip(" ;") for part in re.split(r"\s*•\s*", normalized) if part.strip(" ;")]
    if len(raw_parts) < 2:
        return []
    head = raw_parts[0]
    bullet_items = [f"• {part}" for part in raw_parts[1:]]
    return [head, *bullet_items]


def _split_sentence_like_units(text: str) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    return [
        part.strip()
        for part in re.split(r"(?<=[.!?;:])\s+(?=[A-Z\"(•])", normalized)
        if part.strip()
    ]


def _group_text_units(parts: list[str], *, max_chars: int) -> list[str]:
    grouped: list[str] = []
    buffer: list[str] = []
    for part in parts:
        candidate = " ".join([*buffer, part]).strip()
        if candidate and len(candidate) <= max_chars:
            buffer.append(part)
            continue
        if buffer:
            grouped.append(" ".join(buffer).strip())
        buffer = [part]
    if buffer:
        grouped.append(" ".join(buffer).strip())
    return grouped


def _split_subdivisions(text: str, pattern: re.Pattern[str]) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    matches = list(pattern.finditer(normalized))
    if not matches:
        return []

    parts: list[str] = []
    first_start = matches[0].start()
    preamble = normalized[:first_start].strip()
    if preamble:
        parts.append(preamble)

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        part = normalized[start:end].strip()
        if part:
            parts.append(part)
    return parts


__all__ = [
    "ARTICLE_SPLITTERS",
    "DOCUMENT_ROOT_SPLITTERS",
    "OVERSIZED_SECTION_SPLITTERS",
    "ChunkSplit",
    "group_paragraphs",
    "is_definition_schedule",
    "split_by_chars",
    "split_definition_schedule",
    "split_guidance_point",
    "split_paragraph_units",
    "split_paragraphs",
]
