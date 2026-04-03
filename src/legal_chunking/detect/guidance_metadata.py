"""Safe metadata extraction for guidance/review points."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from legal_chunking.profiles import resolve_profile

RE_SOURCE_CASE_NUMBER = re.compile(r"№\s*([A-Za-zА-Яа-я0-9\-\/]+)")
RE_SOURCE_CASE_DATE = re.compile(
    r"от\s+([0-9]{1,2}\s+[А-Яа-я]+(?:\s+[0-9]{4})?\s*г?\.?)",
    re.IGNORECASE,
)
RE_TAIL_CASE_REFERENCE = re.compile(
    r"(от\s+[0-9]{1,2}\s+[А-Яа-я]+(?:\s+[0-9]{4})?\s*г?\.?\s*№\s*[A-Za-zА-Яа-я0-9\-\/]+)",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class GuidancePointMetadata:
    point_number: str | None
    source_case_reference: str | None = None
    source_case_number: str | None = None
    source_case_date: str | None = None
    source_case_court: str | None = None


@dataclass(slots=True, frozen=True)
class SourceCaseReference:
    reference: str
    number: str | None
    date: str | None
    court: str | None


@dataclass(slots=True, frozen=True)
class _GuidanceMetadataConfig:
    source_reference_pattern: re.Pattern[str] | None
    trailing_note_pattern: re.Pattern[str] | None
    court_patterns: tuple[tuple[re.Pattern[str], str], ...]


def extract_guidance_point_metadata(
    text: str,
    *,
    point_number: str | None,
    profile: str = "generic",
) -> GuidancePointMetadata:
    cleaned = (text or "").strip()
    if not cleaned:
        return GuidancePointMetadata(point_number=point_number)
    config = _load_guidance_metadata_config(profile)
    metadata_view = _strip_trailing_guidance_note(cleaned, config)
    source_case = _parse_source_case_reference(metadata_view, config=config)

    return GuidancePointMetadata(
        point_number=point_number,
        source_case_reference=source_case.reference if source_case is not None else None,
        source_case_number=source_case.number if source_case is not None else None,
        source_case_date=source_case.date if source_case is not None else None,
        source_case_court=source_case.court if source_case is not None else None,
    )


@lru_cache(maxsize=16)
def _load_guidance_metadata_config(profile: str) -> _GuidanceMetadataConfig:
    payload = resolve_profile(profile).guidance_patterns

    prefixes = _normalize_string_list(payload.get("source_reference_prefixes"))
    note_markers = _normalize_string_list(payload.get("trailing_note_markers"))
    court_aliases = payload.get("court_aliases")

    source_reference_pattern = _compile_source_reference_pattern(prefixes)
    trailing_note_pattern = _compile_trailing_note_pattern(note_markers)
    court_patterns = _compile_court_patterns(court_aliases)
    return _GuidanceMetadataConfig(
        source_reference_pattern=source_reference_pattern,
        trailing_note_pattern=trailing_note_pattern,
        court_patterns=court_patterns,
    )


def _parse_source_case_reference(
    metadata_view: str,
    *,
    config: _GuidanceMetadataConfig,
) -> SourceCaseReference | None:
    reference = _find_source_case_reference_candidate(metadata_view, config=config)
    if reference is None:
        return None
    return SourceCaseReference(
        reference=reference,
        number=_extract_source_case_number(reference),
        date=_extract_source_case_date(reference),
        court=_extract_source_case_court(reference, context=metadata_view, config=config),
    )


def _find_source_case_reference_candidate(
    metadata_view: str,
    *,
    config: _GuidanceMetadataConfig,
) -> str | None:
    source_reference_match = (
        config.source_reference_pattern.search(metadata_view)
        if config.source_reference_pattern is not None
        else None
    )
    if source_reference_match is not None:
        return source_reference_match.group(1).strip()

    tail_reference_matches = list(RE_TAIL_CASE_REFERENCE.finditer(metadata_view))
    if tail_reference_matches:
        return tail_reference_matches[-1].group(1).strip()
    return None


def _extract_source_case_number(reference: str) -> str | None:
    number_match = RE_SOURCE_CASE_NUMBER.search(reference)
    return number_match.group(1).strip() if number_match is not None else None


def _extract_source_case_date(reference: str) -> str | None:
    date_match = RE_SOURCE_CASE_DATE.search(reference)
    return date_match.group(1).strip() if date_match is not None else None


def _extract_source_case_court(
    reference: str,
    *,
    context: str,
    config: _GuidanceMetadataConfig,
) -> str | None:
    for pattern, court_label in config.court_patterns:
        if pattern.search(reference):
            return court_label
    for pattern, court_label in config.court_patterns:
        if pattern.search(context):
            return court_label
    return None


def _strip_trailing_guidance_note(text: str, config: _GuidanceMetadataConfig) -> str:
    if config.trailing_note_pattern is None:
        return text
    return config.trailing_note_pattern.sub("", text).strip()


def _compile_source_reference_pattern(prefixes: tuple[str, ...]) -> re.Pattern[str] | None:
    if not prefixes:
        return None
    prefix_group = "|".join(re.escape(prefix) for prefix in prefixes)
    return re.compile(
        rf"((?:{prefix_group})\s+[^.\n]{{0,160}}?(?:от\s+[0-9]{{1,2}}\s+[А-Яа-я]+(?:\s+[0-9]{{4}})?\s*г?\.?)?\s*№\s*[A-Za-zА-Яа-я0-9\-\/]+\.?)",
        re.IGNORECASE,
    )


def _compile_trailing_note_pattern(markers: tuple[str, ...]) -> re.Pattern[str] | None:
    if not markers:
        return None
    marker_group = "|".join(re.escape(marker) for marker in markers)
    return re.compile(
        rf"\b\d{{1,2}}\s+(?:{marker_group})\b.*$",
        re.IGNORECASE | re.DOTALL,
    )


def _compile_court_patterns(payload: Any) -> tuple[tuple[re.Pattern[str], str], ...]:
    if not isinstance(payload, list):
        return ()

    patterns: list[tuple[re.Pattern[str], str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        aliases = _normalize_string_list(item.get("aliases"))
        if not label or not aliases:
            continue
        for alias in aliases:
            patterns.append((re.compile(re.escape(alias), re.IGNORECASE), label))
    return tuple(patterns)


def _normalize_string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return tuple(normalized)


__all__ = [
    "GuidancePointMetadata",
    "SourceCaseReference",
    "extract_guidance_point_metadata",
]
