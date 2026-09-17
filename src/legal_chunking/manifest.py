"""Packaged asset loading and manifest resolution for legal-chunking."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any

from legal_chunking.errors import AssetConfigError

ASSETS_PACKAGE = "legal_chunking.assets"
MANIFEST_FILENAME = "manifest.v1.json"


@dataclass(slots=True, frozen=True)
class ProfileAssetPointers:
    heading_patterns: str
    numbering_markers: str
    chunking_policy: str
    guidance_extractors: str = ""
    reference_patterns: str = ""
    normalization_policy: str = ""


@dataclass(slots=True, frozen=True)
class ReferenceDocFamily:
    id: str
    kind: str
    aliases: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class ProfileReferenceConfig:
    enabled: bool
    require_doc_family: bool = False
    match_mode: str = "family_first"
    doc_families: tuple[ReferenceDocFamily, ...] = ()


@dataclass(slots=True, frozen=True)
class ProfileManifest:
    code: str
    enabled: bool
    aliases: tuple[str, ...] = ()
    language: str | None = None
    reference: ProfileReferenceConfig | None = None
    assets: ProfileAssetPointers | None = None


@dataclass(slots=True, frozen=True)
class AssetManifest:
    version: int
    updated_at: str | None
    profiles: Mapping[str, ProfileManifest] = field(default_factory=dict)

    def enabled_profiles(self) -> set[str]:
        return {code for code, profile in self.profiles.items() if profile.enabled}


@lru_cache(maxsize=64)
def _read_packaged_json(filename: str) -> dict[str, Any]:
    if not filename or filename.startswith("/") or ".." in filename.split("/"):
        raise AssetConfigError(f"Invalid packaged asset path: {filename!r}")
    try:
        payload = json.loads(files(ASSETS_PACKAGE).joinpath(filename).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AssetConfigError(f"Cannot load packaged JSON asset {filename}") from exc
    if not isinstance(payload, Mapping):
        raise AssetConfigError(f"Packaged asset {filename} must be a JSON object")
    return payload


def _normalize_aliases(raw_aliases: object) -> tuple[str, ...]:
    if not isinstance(raw_aliases, list) or not all(isinstance(a, str) for a in raw_aliases):
        raise AssetConfigError("Manifest aliases must be a list of strings")
    aliases: list[str] = []
    for alias in raw_aliases:
        normalized = str(alias).strip().lower()
        if normalized:
            aliases.append(normalized)
    return tuple(aliases)


def _parse_manifest(payload: dict[str, Any]) -> AssetManifest:
    profiles: dict[str, ProfileManifest] = {}
    raw_profiles = payload.get("profiles", {})
    if not isinstance(raw_profiles, Mapping):
        raise AssetConfigError("Manifest field 'profiles' must be an object")

    for code, entry in raw_profiles.items():
        if not isinstance(entry, Mapping):
            raise AssetConfigError(f"Manifest profile entry must be an object for {code}")
        assets = entry.get("assets", {})
        if not isinstance(assets, Mapping):
            raise AssetConfigError(f"Manifest assets entry must be an object for {code}")
        raw_reference = entry.get("reference")
        reference: ProfileReferenceConfig | None = None
        if raw_reference is not None:
            if not isinstance(raw_reference, Mapping):
                raise AssetConfigError(f"Manifest reference entry must be an object for {code}")
            raw_doc_families = raw_reference.get("doc_families", [])
            if not isinstance(raw_doc_families, list):
                raise AssetConfigError(f"Manifest doc_families entry must be a list for {code}")
            doc_families: list[ReferenceDocFamily] = []
            for item in raw_doc_families:
                if not isinstance(item, Mapping):
                    raise AssetConfigError(
                        f"Manifest doc_family entry must be an object for {code}"
                    )
                doc_families.append(
                    ReferenceDocFamily(
                        id=str(item.get("id") or "").strip(),
                        kind=str(item.get("kind") or "").strip(),
                        aliases=_normalize_aliases(item.get("aliases", [])),
                    )
                )
            reference = ProfileReferenceConfig(
                enabled=bool(raw_reference.get("enabled", False)),
                require_doc_family=bool(raw_reference.get("require_doc_family", False)),
                match_mode=str(raw_reference.get("match_mode") or "family_first").strip().lower(),
                doc_families=tuple(doc_families),
            )
        pointers = ProfileAssetPointers(
            heading_patterns=str(assets.get("heading_patterns") or ""),
            numbering_markers=str(assets.get("numbering_markers") or ""),
            chunking_policy=str(assets.get("chunking_policy") or ""),
            guidance_extractors=str(assets.get("guidance_extractors") or ""),
            reference_patterns=str(assets.get("reference_patterns") or ""),
            normalization_policy=str(assets.get("normalization_policy") or ""),
        )
        profiles[code] = ProfileManifest(
            code=code,
            enabled=bool(entry.get("enabled", False)),
            aliases=_normalize_aliases(entry.get("aliases", [])),
            language=str(entry.get("language")).strip().lower() if entry.get("language") else None,
            reference=reference,
            assets=pointers,
        )

    alias_owners = {code: code for code in profiles}
    for code, profile in profiles.items():
        if not profile.enabled:
            continue
        for alias in profile.aliases:
            if alias in alias_owners and alias_owners[alias] != code:
                raise AssetConfigError(f"Ambiguous profile alias: {alias}")
            alias_owners[alias] = code

    return AssetManifest(
        version=int(payload.get("version", 1)),
        updated_at=payload.get("updated_at"),
        profiles=MappingProxyType(profiles),
    )


@lru_cache(maxsize=1)
def load_manifest() -> AssetManifest:
    """Load the packaged asset manifest."""
    return _parse_manifest(_read_packaged_json(MANIFEST_FILENAME))


def load_asset_json(filename: str) -> dict[str, Any]:
    """Load one packaged JSON asset by filename."""
    return deepcopy(_read_packaged_json(filename))
