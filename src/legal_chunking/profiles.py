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
