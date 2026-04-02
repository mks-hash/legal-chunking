"""Asset-backed numbering marker helpers for legal reference normalization."""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

from legal_chunking.profiles import resolve_profile


@lru_cache(maxsize=32)
def _load_numbering_markers(profile: str) -> dict[str, object]:
    payload = resolve_profile(profile).numbering_markers
    if not isinstance(payload, dict):
        return {}
    return payload


@lru_cache(maxsize=64)
def _family_aliases(profile: str, family: str) -> tuple[str, ...]:
    payload = _load_numbering_markers(profile)
    families = payload.get("families")
    if not isinstance(families, dict):
        return ()
    aliases = families.get(family)
    if not isinstance(aliases, list):
        return ()
    seen: set[str] = set()
    ordered: list[str] = []
    for alias in aliases:
        normalized = str(alias).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return tuple(ordered)


@lru_cache(maxsize=128)
def build_numbering_marker_pattern(*, profile: str, family: str) -> str:
    aliases = _family_aliases(profile, family)
    if not aliases:
        return r"(?!x)x"
    parts = sorted((re.escape(alias) for alias in aliases), key=len, reverse=True)
    return "(?:" + "|".join(parts) + ")"


def get_numbering_family_aliases(*, profile: str, family: str) -> list[str]:
    return list(_family_aliases(profile, family))


@lru_cache(maxsize=128)
def _collect_numbering_aliases(profile: str, families: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for family in families:
        for alias in _family_aliases(profile, family):
            key = alias.casefold()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(alias)
    return tuple(ordered)


def get_numbering_aliases(*, profile: str, families: Iterable[str]) -> list[str]:
    family_tuple = tuple(str(family).strip() for family in families if str(family).strip())
    if not family_tuple:
        return []
    return list(_collect_numbering_aliases(profile, family_tuple))


__all__ = [
    "build_numbering_marker_pattern",
    "get_numbering_aliases",
    "get_numbering_family_aliases",
]
