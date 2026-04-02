"""Deterministic hashing helpers for normalized chunk inputs."""

from __future__ import annotations

import hashlib

from legal_chunking.normalize import normalize_chunk_text, normalize_embedding_text

PIPELINE_ID = "legal-chunking"
PIPELINE_VERSION = "0.1.0"


def compute_semantic_hash(text: str) -> str:
    """Hash normalized semantic content only."""
    normalized = normalize_chunk_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_chunk_input_hash(
    *,
    text: str,
    profile: str,
    pipeline_version: str = PIPELINE_VERSION,
) -> str:
    """Hash normalized chunk inputs including stable pipeline metadata."""
    normalized = normalize_chunk_text(text)
    raw = f"{PIPELINE_ID}:{pipeline_version}:{profile}:{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_embedding_input_hash(
    *,
    text: str,
    embedder_id: str,
    embedder_version: str,
) -> str:
    """Hash normalized embedding inputs for future downstream use."""
    normalized = normalize_embedding_text(text)
    raw = f"{embedder_id}:{embedder_version}:{normalized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
