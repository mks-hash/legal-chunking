"""OSS-friendly domain models for legal document chunking."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from legal_chunking.tracing import TraceReport


class LegalUnitType(StrEnum):
    SECTION = "section"
    RULE_BLOCK = "rule_block"
    REVIEW_POINT = "review_point"
    GUIDANCE_POINT = "guidance_point"
    DEFINITION_ENTRY = "definition_entry"
    SCHEDULE = "schedule"
    PARAGRAPH = "paragraph"


@dataclass(slots=True)
class LegalMetadata:
    article_number: str | None = None
    paragraph_number: str | None = None
    point_number: str | None = None
    legal_unit_type: LegalUnitType | None = None
    legal_unit_number: str | None = None
    source_case_reference: str | None = None
    source_case_number: str | None = None
    source_case_date: str | None = None
    source_case_court: str | None = None
    definition_term: str | None = None


@dataclass(slots=True)
class Section:
    section_id: str
    kind: str
    title: str
    order: int
    parent_section_id: str | None = None
    path: list[str] = field(default_factory=list)
    section_type: str | None = None
    metadata: LegalMetadata = field(default_factory=LegalMetadata)
    start_offset: int = 0
    end_offset: int = 0
    text: str = ""


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    text: str
    order: int
    chunk_method: str = "by_section"
    page: int | None = None
    section_id: str | None = None
    section_title: str | None = None
    section_type: str | None = None
    metadata: LegalMetadata = field(default_factory=LegalMetadata)
    semantic_hash: str = ""
    prev_chunk_id: str | None = None
    next_chunk_id: str | None = None


@dataclass(slots=True)
class Document:
    source_name: str
    profile: str
    language: str | None
    text: str
    chunk_policy: str = "default"
    sections: list[Section] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    trace: TraceReport | None = None
