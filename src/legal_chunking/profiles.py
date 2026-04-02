"""Profile resolution over packaged manifest and policy assets."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from legal_chunking.manifest import load_asset_json, load_manifest


@dataclass(slots=True)
class ResolvedProfile:
    code: str
    language: str | None
    heading_patterns: dict[str, Any]
    numbering_markers: dict[str, Any]
    chunking_policy: dict[str, Any]


@dataclass(slots=True, frozen=True)
class ChunkFallbackConfig:
    max_chars: int
    overlap_chars: int


ALLOWED_CHUNK_POLICIES = {"default", "statute", "guidance", "case_law"}


@lru_cache(maxsize=32)
def resolve_profile(profile: str) -> ResolvedProfile:
    """Resolve one enabled profile by code or alias."""
    normalized = (profile or "").strip().lower() or "generic"
    manifest = load_manifest()

    direct = manifest.profiles.get(normalized)
    if direct and direct.enabled and direct.assets is not None:
        return ResolvedProfile(
            code=direct.code,
            language=direct.language,
            heading_patterns=load_asset_json(direct.assets.heading_patterns),
            numbering_markers=load_asset_json(direct.assets.numbering_markers),
            chunking_policy=load_asset_json(direct.assets.chunking_policy),
        )

    for candidate in manifest.profiles.values():
        if not candidate.enabled or candidate.assets is None:
            continue
        if normalized in candidate.aliases:
            return ResolvedProfile(
                code=candidate.code,
                language=candidate.language,
                heading_patterns=load_asset_json(candidate.assets.heading_patterns),
                numbering_markers=load_asset_json(candidate.assets.numbering_markers),
                chunking_policy=load_asset_json(candidate.assets.chunking_policy),
            )

    raise ValueError(f"Unknown or disabled profile: {profile}")


def select_chunk_policy(
    chunking_policy: dict[str, Any],
    *,
    doc_kind: str | None = None,
) -> str:
    """Resolve one allowed chunking policy from the profile asset."""
    defaults = chunking_policy.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("Chunking policy payload must contain an object in 'defaults'")

    normalized_kind = (doc_kind or "").strip().lower()
    selected = defaults.get(normalized_kind) or defaults.get("code") or defaults.get("other")
    policy = str(selected or "default").strip().lower()
    if policy not in ALLOWED_CHUNK_POLICIES:
        raise ValueError(f"Unsupported chunk policy '{policy}'")
    return policy


def select_chunk_fallback(chunking_policy: dict[str, Any]) -> ChunkFallbackConfig:
    """Resolve deterministic char-budget fallback settings from the profile asset."""
    payload = chunking_policy.get("fallback", {})
    if not isinstance(payload, dict):
        raise ValueError("Chunking policy payload must contain an object in 'fallback'")

    max_chars = int(payload.get("max_chars", 1200))
    overlap_chars = int(payload.get("overlap_chars", 120))
    if max_chars <= 0:
        raise ValueError("Chunk fallback max_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("Chunk fallback overlap_chars must be non-negative")
    if overlap_chars >= max_chars:
        raise ValueError("Chunk fallback overlap_chars must be smaller than max_chars")
    return ChunkFallbackConfig(max_chars=max_chars, overlap_chars=overlap_chars)
