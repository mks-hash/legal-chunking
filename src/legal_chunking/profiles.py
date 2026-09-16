"""Profile resolution over packaged manifest and policy assets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legal_chunking.errors import AssetConfigError, InvalidProfileError
from legal_chunking.manifest import ReferenceDocFamily, load_asset_json, load_manifest
from legal_chunking.runtime_policy import RuntimePolicy, parse_runtime_policy


@dataclass(slots=True, frozen=True)
class ResolvedProfile:
    code: str
    language: str | None
    heading_patterns: dict[str, Any]
    numbering_markers: dict[str, Any]
    chunking_policy: dict[str, Any]
    runtime: RuntimePolicy
    guidance_extractors: dict[str, Any]
    reference_patterns: dict[str, Any]
    normalization_policy: dict[str, Any]
    doc_families: tuple[ReferenceDocFamily, ...]


@dataclass(slots=True, frozen=True)
class ChunkFallbackConfig:
    max_chars: int
    overlap_chars: int


@dataclass(slots=True, frozen=True)
class _DocFamilyAliasHit:
    family: ReferenceDocFamily
    start: int
    end: int
    alias_length: int


ALLOWED_CHUNK_POLICIES = {"default", "statute", "guidance", "case_law"}


def resolve_profile(profile: str) -> ResolvedProfile:
    """Resolve one enabled profile by code or alias."""
    normalized = (profile or "").strip().lower() or "generic"
    manifest = load_manifest()

    selected = manifest.profiles.get(normalized)
    if selected is None:
        selected = next(
            (p for p in manifest.profiles.values() if p.enabled and normalized in p.aliases), None
        )
    if selected is None or not selected.enabled or selected.assets is None:
        raise InvalidProfileError(f"Unknown or disabled profile: {profile}")
    assets = selected.assets
    chunking_policy = load_asset_json(assets.chunking_policy)
    return ResolvedProfile(
        code=selected.code,
        language=selected.language,
        heading_patterns=load_asset_json(assets.heading_patterns),
        numbering_markers=load_asset_json(assets.numbering_markers),
        chunking_policy=chunking_policy,
        runtime=parse_runtime_policy(chunking_policy),
        guidance_extractors=load_asset_json(assets.guidance_extractors)
        if assets.guidance_extractors
        else {},
        reference_patterns=load_asset_json(assets.reference_patterns)
        if assets.reference_patterns
        else {},
        normalization_policy=load_asset_json(assets.normalization_policy)
        if assets.normalization_policy
        else {},
        doc_families=selected.reference.doc_families if selected.reference else (),
    )


def select_chunk_policy(
    chunking_policy: dict[str, Any],
    *,
    doc_kind: str | None = None,
) -> str:
    """Resolve one allowed chunking policy from the profile asset."""
    defaults = chunking_policy.get("defaults", {})
    if not isinstance(defaults, dict):
        raise AssetConfigError("Chunking policy payload must contain an object in 'defaults'")

    normalized_kind = (doc_kind or "").strip().lower()
    if normalized_kind:
        selected = defaults.get(normalized_kind) or defaults.get("other") or defaults.get("code")
    else:
        selected = defaults.get("code") or defaults.get("other")
    policy = str(selected or "default").strip().lower()
    if policy not in ALLOWED_CHUNK_POLICIES:
        raise AssetConfigError(f"Unsupported chunk policy '{policy}'")
    return policy


def select_chunk_fallback(chunking_policy: dict[str, Any]) -> ChunkFallbackConfig:
    """Resolve deterministic char-budget fallback settings from the profile asset."""
    payload = chunking_policy.get("fallback", {})
    if not isinstance(payload, dict):
        raise ValueError("Chunking policy payload must contain an object in 'fallback'")

    max_chars = payload.get("max_chars", 1200)
    overlap_chars = payload.get("overlap_chars", 120)
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (max_chars, overlap_chars)):
        raise AssetConfigError("Chunk fallback budgets must be integers")
    if max_chars <= 0:
        raise AssetConfigError("Chunk fallback max_chars must be positive")
    if overlap_chars < 0:
        raise AssetConfigError("Chunk fallback overlap_chars must be non-negative")
    if overlap_chars >= max_chars:
        raise AssetConfigError("Chunk fallback overlap_chars must be smaller than max_chars")
    return ChunkFallbackConfig(max_chars=max_chars, overlap_chars=overlap_chars)


def resolve_doc_family(profile: str, text: str) -> ReferenceDocFamily | None:
    """Resolve one doc family by manifest aliases, if any."""
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    hits = find_doc_family_alias_hits(profile, normalized)
    if not hits:
        return None
    return max(hits, key=lambda hit: (hit.alias_length, -hit.start)).family


def resolve_doc_family_near(
    profile: str,
    text_or_hits: str | tuple[_DocFamilyAliasHit, ...],
    *,
    anchor_start: int,
    anchor_end: int,
) -> ReferenceDocFamily | None:
    """Resolve the nearest doc-family alias to one citation span."""
    if isinstance(text_or_hits, tuple):
        hits = text_or_hits
    else:
        normalized = (text_or_hits or "").strip().lower()
        if not normalized:
            return None
        hits = find_doc_family_alias_hits(profile, normalized)
    if not hits:
        return None
    best_hit = min(
        hits,
        key=lambda hit: (
            _alias_distance(anchor_start, anchor_end, hit.start, hit.end),
            -hit.alias_length,
            hit.start,
        ),
    )
    return best_hit.family


def find_doc_family_alias_hits(
    profile: str,
    normalized_text: str,
) -> tuple[_DocFamilyAliasHit, ...]:
    hits: list[_DocFamilyAliasHit] = []
    for family in resolve_profile(profile).doc_families:
        for alias in family.aliases:
            if not alias:
                continue
            offset = normalized_text.find(alias)
            while offset != -1:
                end = offset + len(alias)
                left_joined = (
                    alias[0].isalnum()
                    and offset > 0
                    and (
                        normalized_text[offset - 1].isalnum() or normalized_text[offset - 1] == "_"
                    )
                )
                right_joined = (
                    alias[-1].isalnum()
                    and end < len(normalized_text)
                    and (normalized_text[end].isalnum() or normalized_text[end] == "_")
                )
                if left_joined or right_joined:
                    offset = normalized_text.find(alias, offset + 1)
                    continue
                hits.append(
                    _DocFamilyAliasHit(
                        family=family,
                        start=offset,
                        end=offset + len(alias),
                        alias_length=len(alias),
                    )
                )
                offset = normalized_text.find(alias, offset + 1)
    return tuple(hits)


def _alias_distance(anchor_start: int, anchor_end: int, alias_start: int, alias_end: int) -> int:
    if alias_end <= anchor_start:
        return anchor_start - alias_end
    if alias_start >= anchor_end:
        return alias_start - anchor_end
    return 0


__all__ = [
    "ChunkFallbackConfig",
    "ResolvedProfile",
    "find_doc_family_alias_hits",
    "resolve_doc_family",
    "resolve_doc_family_near",
    "resolve_profile",
    "select_chunk_fallback",
    "select_chunk_policy",
]
