"""Asset-backed heading pattern compilation."""

from __future__ import annotations

import re
from functools import lru_cache

from legal_chunking.errors import AssetConfigError
from legal_chunking.profiles import resolve_profile

from .heading_types import ALLOWED_SECTION_TYPES


@lru_cache(maxsize=32)
def compile_heading_patterns(profile: str) -> list[tuple[str, re.Pattern[str]]]:
    """Compile asset-backed heading patterns for one resolved profile."""
    payload = resolve_profile(profile).heading_patterns
    patterns = payload.get("patterns", [])
    if not isinstance(patterns, list):
        raise AssetConfigError("Heading patterns payload must contain a list in 'patterns'")

    compiled: list[tuple[str, re.Pattern[str]]] = []
    for item in patterns:
        if not isinstance(item, dict):
            raise AssetConfigError("Heading pattern entry must be an object")
        section_type = str(item.get("section_type") or "").strip()
        regex = str(item.get("regex") or "").strip()
        if not section_type or not regex:
            raise AssetConfigError(f"Invalid heading pattern entry: {item}")
        if section_type not in ALLOWED_SECTION_TYPES:
            raise AssetConfigError(f"Unsupported section_type '{section_type}'")
        compiled.append((section_type, re.compile(regex, re.IGNORECASE)))
    return compiled


__all__ = ["compile_heading_patterns"]
