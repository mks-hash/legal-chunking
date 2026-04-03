"""Safe metadata extraction for guidance/review points."""

from __future__ import annotations

import re
from dataclasses import dataclass

RE_SOURCE_CASE_REFERENCE = re.compile(
    r"(Определение\s+[^.\n]{0,160}?(?:от\s+[0-9]{1,2}\s+[А-Яа-я]+(?:\s+[0-9]{4})?\s*г?\.?)?\s*№\s*[A-Za-zА-Яа-я0-9\-\/]+\.?)",
    re.IGNORECASE,
)
RE_SOURCE_CASE_NUMBER = re.compile(r"№\s*([A-Za-zА-Яа-я0-9\-\/]+)")
RE_SOURCE_CASE_DATE = re.compile(
    r"от\s+([0-9]{1,2}\s+[А-Яа-я]+(?:\s+[0-9]{4})?\s*г?\.?)",
    re.IGNORECASE,
)
RE_TAIL_CASE_REFERENCE = re.compile(
    r"(от\s+[0-9]{1,2}\s+[А-Яа-я]+(?:\s+[0-9]{4})?\s*г?\.?\s*№\s*[A-Za-zА-Яа-я0-9\-\/]+)",
    re.IGNORECASE,
)
RE_TRAILING_SEE_ALSO_NOTE = re.compile(r"\b\d{1,2}\s+См\.\s+также\b.*$", re.IGNORECASE | re.DOTALL)
COURT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"судебн(?:ая|ой)\s+коллег(?:ия|ии)\s+[^.\n]{0,80}?верховн(?:ого|ый)\s+суда\s+рф",
            re.IGNORECASE,
        ),
        "Верховный Суд РФ",
    ),
    (
        re.compile(r"верховн(?:ого|ый)\s+суда\s+рф", re.IGNORECASE),
        "Верховный Суд РФ",
    ),
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


def extract_guidance_point_metadata(
    text: str,
    *,
    point_number: str | None,
) -> GuidancePointMetadata:
    cleaned = (text or "").strip()
    if not cleaned:
        return GuidancePointMetadata(point_number=point_number)
    metadata_view = RE_TRAILING_SEE_ALSO_NOTE.sub("", cleaned).strip()
    source_case = _parse_source_case_reference(metadata_view)

    return GuidancePointMetadata(
        point_number=point_number,
        source_case_reference=source_case.reference if source_case is not None else None,
        source_case_number=source_case.number if source_case is not None else None,
        source_case_date=source_case.date if source_case is not None else None,
        source_case_court=source_case.court if source_case is not None else None,
    )


def _parse_source_case_reference(metadata_view: str) -> SourceCaseReference | None:
    reference = _find_source_case_reference_candidate(metadata_view)
    if reference is None:
        return None
    return SourceCaseReference(
        reference=reference,
        number=_extract_source_case_number(reference),
        date=_extract_source_case_date(reference),
        court=_extract_source_case_court(reference, context=metadata_view),
    )


def _find_source_case_reference_candidate(metadata_view: str) -> str | None:
    source_reference_match = RE_SOURCE_CASE_REFERENCE.search(metadata_view)
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


def _extract_source_case_court(reference: str, *, context: str) -> str | None:
    for pattern, court_label in COURT_PATTERNS:
        if pattern.search(reference):
            return court_label
    for pattern, court_label in COURT_PATTERNS:
        if pattern.search(context):
            return court_label
    return None


__all__ = [
    "GuidancePointMetadata",
    "SourceCaseReference",
    "extract_guidance_point_metadata",
]
