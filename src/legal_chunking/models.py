"""OSS-friendly domain models for legal document chunking."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Section:
    section_id: str
    kind: str
    title: str
    order: int
    parent_section_id: str | None = None
    path: list[str] = field(default_factory=list)
    article_number: str | None = None
    paragraph_number: str | None = None
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
    article_number: str | None = None
    paragraph_number: str | None = None
    semantic_hash: str = ""
    prev_chunk_id: str | None = None
    next_chunk_id: str | None = None


@dataclass(slots=True)
class Document:
    source_name: str
    profile: str
    language: str | None
    text: str
    pipeline_version: str = "0.1.0"
    chunk_policy: str = "default"
    sections: list[Section] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
