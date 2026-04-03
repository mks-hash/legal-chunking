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


@dataclass(slots=True, frozen=True)
class GuidancePointMetadata:
    point_number: str | None
    source_case_reference: str | None = None
    source_case_number: str | None = None
    source_case_date: str | None = None
    source_case_court: str | None = None


def extract_guidance_point_metadata(
    text: str,
    *,
    point_number: str | None,
) -> GuidancePointMetadata:
    cleaned = (text or "").strip()
    if not cleaned:
        return GuidancePointMetadata(point_number=point_number)
    metadata_view = RE_TRAILING_SEE_ALSO_NOTE.sub("", cleaned).strip()

    source_reference_match = RE_SOURCE_CASE_REFERENCE.search(metadata_view)
    source_case_reference = (
        source_reference_match.group(1).strip() if source_reference_match else None
    )
    if source_case_reference is None:
        tail_reference_matches = list(RE_TAIL_CASE_REFERENCE.finditer(metadata_view))
        if tail_reference_matches:
            source_case_reference = tail_reference_matches[-1].group(1).strip()
    source_case_number = None
    source_case_date = None
    source_case_court = None
    if source_case_reference:
        number_match = RE_SOURCE_CASE_NUMBER.search(source_case_reference)
        if number_match:
            source_case_number = number_match.group(1).strip()
        date_match = RE_SOURCE_CASE_DATE.search(source_case_reference)
        if date_match:
            source_case_date = date_match.group(1).strip()
        if "Судебной коллегии Верховного Суда" in source_case_reference:
            source_case_court = "Судебная коллегия Верховного Суда РФ"
        elif "Верховного Суда" in source_case_reference:
            source_case_court = "Верховный Суд РФ"
    if source_case_court is None and "Верховного Суда РФ" in metadata_view:
        source_case_court = "Верховный Суд РФ"

    return GuidancePointMetadata(
        point_number=point_number,
        source_case_reference=source_case_reference,
        source_case_number=source_case_number,
        source_case_date=source_case_date,
        source_case_court=source_case_court,
    )


__all__ = [
    "GuidancePointMetadata",
    "extract_guidance_point_metadata",
]
