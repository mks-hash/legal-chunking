"""Deterministic text normalization contracts for legal-chunking."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_INLINE_WHITESPACE_RE = re.compile(r"[ \t\v]+")
_NBSP_RE = re.compile(r"[\u00A0\u202F\u2009]")
_INLINE_HYPHEN_RE = re.compile(r"(?<=\w)\s*-\s*(?=\w)")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def normalize_chunk_text(text: str) -> str:
    """Normalize chunk text for hashing and stable downstream inputs."""
    normalized = (text or "").strip()
    return _WHITESPACE_RE.sub(" ", normalized)


def normalize_embedding_text(text: str) -> str:
    """Normalize embedding text using the same current chunk contract."""
    return normalize_chunk_text(text)


def normalize_extracted_text(text: str) -> str:
    """Apply format-generic extraction cleanup while preserving boundaries."""
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\x00", "").replace("\f", "\n")
    normalized = _NBSP_RE.sub(" ", normalized)
    normalized = normalized.replace("\u00ad", "").replace("\u2011", "-")
    lines = []
    for line in normalized.split("\n"):
        cleaned = _INLINE_HYPHEN_RE.sub("-", line)
        cleaned = _INLINE_WHITESPACE_RE.sub(" ", cleaned).strip()
        lines.append(cleaned)
    normalized = "\n".join(lines)
    normalized = _MULTI_NEWLINE_RE.sub("\n\n", normalized)
    return normalized.strip()
