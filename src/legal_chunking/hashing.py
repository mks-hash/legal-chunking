"""Deterministic hashing helpers for normalized chunk inputs."""

from __future__ import annotations

import hashlib

from legal_chunking.normalize import normalize_chunk_text


def compute_semantic_hash(text: str) -> str:
    """Hash normalized semantic content only."""
    normalized = normalize_chunk_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _compute_chunk_identity_hash(
    *,
    text: str,
    profile: str,
) -> str:
    """Hash normalized chunk inputs for deterministic chunk identity."""
    normalized = normalize_chunk_text(text)
    raw = f"{profile}:{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
