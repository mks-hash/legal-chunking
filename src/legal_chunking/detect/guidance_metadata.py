"""Safe metadata extraction for guidance/review points."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from legal_chunking.profiles import resolve_profile


@dataclass(slots=True, frozen=True)
class GuidancePointMetadata:
    point_number: str | None
    source_case_reference: str | None = None
    source_case_number: str | None = None
    source_case_date: str | None = None
    source_case_court: str | None = None


@dataclass(slots=True, frozen=True)
class SourceCaseMetadata:
    source_pattern_id: str | None
    reference: str
    number: str | None
    date: str | None
    court: str | None


@dataclass(slots=True, frozen=True)
class _GuidanceMetadataConfig:
    supported_doc_kind: str | None
    supported_scope: str | None
    strip_patterns: tuple[re.Pattern[str], ...]
    candidate_patterns: tuple[_CandidatePattern, ...]
    case_number_pattern: re.Pattern[str] | None
    case_date_pattern: re.Pattern[str] | None
    court_patterns: tuple[tuple[re.Pattern[str], str], ...]


@dataclass(slots=True, frozen=True)
class _CandidatePattern:
    pattern_id: str
    pattern: re.Pattern[str]
    select: str


@dataclass(slots=True, frozen=True)
class _SourceCaseCandidate:
    pattern_id: str
    reference: str


def extract_guidance_point_metadata(
    text: str,
    *,
    point_number: str | None,
    profile: str = "generic",
    doc_kind: str | None = None,
    extractor_scope: str = "review_point",
) -> GuidancePointMetadata:
    cleaned = (text or "").strip()
    if not cleaned:
        return GuidancePointMetadata(point_number=point_number)
    config = _load_guidance_metadata_config(
        profile,
        doc_kind=(doc_kind or "").strip().lower() or None,
        extractor_scope=extractor_scope,
    )
    metadata_view = _normalize_metadata_view(
        cleaned,
        config=config,
        doc_kind=doc_kind,
        extractor_scope=extractor_scope,
    )
    source_case = _parse_source_case_metadata(metadata_view, config=config)

    return GuidancePointMetadata(
        point_number=point_number,
        source_case_reference=source_case.reference if source_case is not None else None,
        source_case_number=source_case.number if source_case is not None else None,
        source_case_date=source_case.date if source_case is not None else None,
        source_case_court=source_case.court if source_case is not None else None,
    )


@lru_cache(maxsize=32)
def _load_guidance_metadata_config(
    profile: str,
    *,
    doc_kind: str | None,
    extractor_scope: str,
) -> _GuidanceMetadataConfig:
    payload = resolve_profile(profile).guidance_extractors
    scope_payload = payload.get("scope", {}) if isinstance(payload, dict) else {}
    field_patterns = payload.get("field_patterns", {}) if isinstance(payload, dict) else {}
    supported_doc_kind = _normalize_optional_string(scope_payload.get("doc_kind"))
    supported_scope = _normalize_optional_string(scope_payload.get("extractor_scope"))

    strip_patterns = _compile_regex_sequence(payload.get("strip_patterns"))
    candidate_patterns = _compile_candidate_patterns(payload.get("candidate_patterns"))
    case_number_pattern = _compile_field_pattern(field_patterns, "case_number")
    case_date_pattern = _compile_field_pattern(field_patterns, "case_date")
    court_patterns = _compile_court_patterns(payload.get("court_aliases"))
    return _GuidanceMetadataConfig(
        supported_doc_kind=supported_doc_kind,
        supported_scope=supported_scope,
        strip_patterns=strip_patterns,
        candidate_patterns=candidate_patterns,
        case_number_pattern=case_number_pattern,
        case_date_pattern=case_date_pattern,
        court_patterns=court_patterns,
    )


def _normalize_metadata_view(
    text: str,
    *,
    config: _GuidanceMetadataConfig,
    doc_kind: str | None,
    extractor_scope: str,
) -> str:
    if not _supports_guidance_scope(
        config,
        doc_kind=(doc_kind or "").strip().lower() or None,
        extractor_scope=extractor_scope,
    ):
        return text
    normalized = text
    for pattern in config.strip_patterns:
        normalized = pattern.sub("", normalized).strip()
    return normalized


def _supports_guidance_scope(
    config: _GuidanceMetadataConfig,
    *,
    doc_kind: str | None,
    extractor_scope: str,
) -> bool:
    if config.supported_doc_kind and config.supported_doc_kind != doc_kind:
        return False
    if config.supported_scope and config.supported_scope != extractor_scope:
        return False
    return True


def _parse_source_case_metadata(
    metadata_view: str,
    *,
    config: _GuidanceMetadataConfig,
) -> SourceCaseMetadata | None:
    candidate = _select_source_case_candidate(metadata_view, config=config)
    if candidate is None:
        return None
    return SourceCaseMetadata(
        source_pattern_id=candidate.pattern_id,
        reference=candidate.reference,
        number=_extract_source_case_field(candidate.reference, config.case_number_pattern),
        date=_extract_source_case_field(candidate.reference, config.case_date_pattern),
        court=_extract_source_case_court(candidate.reference, context=metadata_view, config=config),
    )


def _select_source_case_candidate(
    metadata_view: str,
    *,
    config: _GuidanceMetadataConfig,
) -> _SourceCaseCandidate | None:
    for candidate_pattern in config.candidate_patterns:
        matches = list(candidate_pattern.pattern.finditer(metadata_view))
        if not matches:
            continue
        selected = matches[-1] if candidate_pattern.select == "last" else matches[0]
        return _SourceCaseCandidate(
            pattern_id=candidate_pattern.pattern_id,
            reference=selected.group(1).strip(),
        )
    return None


def _extract_source_case_field(reference: str, pattern: re.Pattern[str] | None) -> str | None:
    if pattern is None:
        return None
    match = pattern.search(reference)
    return match.group(1).strip() if match is not None else None


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


def _compile_regex_sequence(payload: Any) -> tuple[re.Pattern[str], ...]:
    if not isinstance(payload, list):
        return ()
    patterns: list[re.Pattern[str]] = []
    for item in payload:
        compiled = _compile_payload_regex(item)
        if compiled is not None:
            patterns.append(compiled)
    return tuple(patterns)


def _compile_candidate_patterns(payload: Any) -> tuple[_CandidatePattern, ...]:
    if not isinstance(payload, list):
        return ()
    patterns: list[_CandidatePattern] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        pattern_id = str(item.get("id") or "").strip()
        select = str(item.get("select") or "first").strip().lower()
        compiled = _compile_payload_regex(item)
        if not pattern_id or compiled is None or select not in {"first", "last"}:
            continue
        patterns.append(
            _CandidatePattern(
                pattern_id=pattern_id,
                pattern=compiled,
                select=select,
            )
        )
    return tuple(patterns)


def _compile_field_pattern(payload: Any, key: str) -> re.Pattern[str] | None:
    if not isinstance(payload, dict):
        return None
    return _compile_payload_regex(payload.get(key))


def _compile_payload_regex(payload: Any) -> re.Pattern[str] | None:
    if not isinstance(payload, dict):
        return None
    pattern_text = str(payload.get("regex") or "").strip()
    if not pattern_text:
        return None
    return re.compile(pattern_text, _parse_regex_flags(payload.get("flags")))


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


def _normalize_optional_string(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def _parse_regex_flags(payload: Any) -> int:
    if not isinstance(payload, list):
        return 0
    flags = 0
    for item in payload:
        name = str(item or "").strip().upper()
        if name == "IGNORECASE":
            flags |= re.IGNORECASE
        elif name == "DOTALL":
            flags |= re.DOTALL
        elif name == "MULTILINE":
            flags |= re.MULTILINE
    return flags


__all__ = [
    "GuidancePointMetadata",
    "SourceCaseMetadata",
    "extract_guidance_point_metadata",
]
