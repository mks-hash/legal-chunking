"""High-level library API."""

from __future__ import annotations

from pathlib import Path

from legal_chunking.chunk import build_chunks
from legal_chunking.detect.sections import assemble_sections
from legal_chunking.models import Document
from legal_chunking.normalize import normalize_extracted_text
from legal_chunking.profiles import resolve_profile, select_chunk_fallback, select_chunk_policy


def chunk_text(
    text: str,
    profile: str = "generic",
    source_name: str = "<memory>",
    doc_kind: str | None = None,
) -> Document:
    """Return deterministic sections and policy-aware chunks for normalized text input."""
    resolved_profile = resolve_profile(profile)
    chunk_policy = select_chunk_policy(resolved_profile.chunking_policy, doc_kind=doc_kind)
    fallback = select_chunk_fallback(resolved_profile.chunking_policy)
    normalized_document = normalize_extracted_text(text)
    sections = assemble_sections(
        normalized_document,
        profile=resolved_profile.code,
        source_name=source_name,
        chunk_policy=chunk_policy,
    )
    chunks = build_chunks(
        sections,
        source_name=source_name,
        profile=resolved_profile.code,
        chunk_policy=chunk_policy,
        fallback=fallback,
    )
    return Document(
        source_name=source_name,
        profile=resolved_profile.code,
        language=resolved_profile.language,
        text=normalized_document,
        chunk_policy=chunk_policy,
        sections=sections,
        chunks=chunks,
    )


def chunk_pdf(path: str | Path, profile: str = "generic") -> Document:
    """Read a PDF path placeholder until PDF extraction is implemented."""
    source = Path(path)
    resolved_profile = resolve_profile(profile)
    chunk_policy = select_chunk_policy(resolved_profile.chunking_policy)
    return Document(
        source_name=source.name,
        profile=resolved_profile.code,
        language=resolved_profile.language,
        text="",
        chunk_policy=chunk_policy,
        chunks=[],
    )
