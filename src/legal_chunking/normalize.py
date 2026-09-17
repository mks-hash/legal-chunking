"""Deterministic text normalization contracts for legal-chunking."""

from __future__ import annotations

import re

from legal_chunking.text_mapping import _TextView

_WHITESPACE_RE = re.compile(r"\s+")
_INLINE_WHITESPACE_RE = re.compile(r"[ \t\v]+")
_NBSP_RE = re.compile(r"[\u00A0\u202F\u2009]")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def normalize_chunk_text(text: str) -> str:
    """Normalize chunk text for hashing and stable downstream inputs."""
    normalized = (text or "").strip()
    return _WHITESPACE_RE.sub(" ", normalized)


def _normalize_extracted_view(view: _TextView) -> _TextView:
    normalized = view.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\x00", "").replace("\f", "\n")
    normalized = normalized.sub(_NBSP_RE, " ")
    normalized = normalized.replace("\u00ad", "").replace("\u2011", "-")
    normalized = normalized.sub(_INLINE_WHITESPACE_RE, " ")
    normalized = normalized.strip_lines()
    return normalized.sub(_MULTI_NEWLINE_RE, "\n\n").strip()


def normalize_extracted_text(text: str) -> str:
    """Apply format-generic extraction cleanup while preserving boundaries."""
    return _normalize_extracted_view(_TextView.from_source(text or "")).text
