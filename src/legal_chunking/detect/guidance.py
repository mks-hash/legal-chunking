"""Guidance/review point detection and safe metadata extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

RE_GUIDANCE_POINT_START = re.compile(
    r"(?m)^(?:(?i:пункт)\s+)?(?P<num>\d{1,3})\.\s+(?=[A-ZА-ЯЁ])",
)
RE_INLINE_GUIDANCE_POINT_START = re.compile(
    r"(?<!\n)[ \t]+(?P<num>\d{1,3})\.\s*\n(?=[A-ZА-ЯЁ])",
)
RE_STANDALONE_PAGE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
RE_FOOTNOTE_LINE = re.compile(r"^\s*\d{1,2}\s+[А-Яа-яA-Za-z].{0,160}$")
RE_GUIDANCE_POINT_CITATION_PREFIX = re.compile(
    r"^(определение\s+судебной\s+коллегии|см\.\s+также)\b",
    re.IGNORECASE,
)
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
class GuidanceBlock:
    method: str
    text: str
    point_number: str | None = None


@dataclass(slots=True, frozen=True)
class GuidancePointMetadata:
    point_number: str | None
    source_case_reference: str | None = None
    source_case_number: str | None = None
    source_case_date: str | None = None
    source_case_court: str | None = None


def split_guidance_blocks(
    text: str,
    *,
    allow_noninitial_sequence: bool = False,
    min_points: int = 3,
) -> list[GuidanceBlock]:
    stripped = (text or "").strip()
    if not stripped:
        return []

    raw_matches = list(RE_GUIDANCE_POINT_START.finditer(stripped))
    matches: list[re.Match[str]] = []
    for match in raw_matches:
        if is_admissible_guidance_point_match(
            stripped,
            match,
            allow_noninitial_sequence=allow_noninitial_sequence,
        ):
            matches.append(match)
    if len(matches) < min_points:
        return [GuidanceBlock(method="guidance_paragraph", text=stripped)]

    point_numbers = [int(match.group("num")) for match in matches if match.group("num").isdigit()]
    if not point_numbers:
        return [GuidanceBlock(method="guidance_paragraph", text=stripped)]
    if not allow_noninitial_sequence and point_numbers[0] != 1:
        return [GuidanceBlock(method="guidance_paragraph", text=stripped)]

    ascending_pairs = sum(
        1
        for previous, current in zip(point_numbers, point_numbers[1:], strict=False)
        if current == previous + 1
    )
    if ascending_pairs < max(0, min_points - 1):
        return _paragraph_guidance_blocks(stripped)

    blocks: list[GuidanceBlock] = []
    first_match = matches[0]
    preamble = stripped[: first_match.start()].strip()
    if preamble:
        blocks.append(GuidanceBlock(method="guidance_preamble", text=preamble))

    for index, match in enumerate(matches):
        block_start = match.start()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(stripped)
        block_text = stripped[block_start:block_end].strip()
        if block_text:
            blocks.append(
                GuidanceBlock(
                    method="guidance_point",
                    text=block_text,
                    point_number=match.group("num"),
                )
            )

    return blocks if blocks else _paragraph_guidance_blocks(stripped)


def normalize_guidance_text(text: str) -> str:
    prepared = RE_INLINE_GUIDANCE_POINT_START.sub(
        lambda match: f"\n{match.group('num')}. ",
        text or "",
    )
    kept: list[str] = []
    for raw_line in prepared.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if is_guidance_page_artifact_line(stripped):
            continue
        kept.append(stripped)
    while kept and kept[-1] == "":
        kept.pop()
    if not kept:
        return ""
    return "\n".join(kept).strip()


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


def _paragraph_guidance_blocks(text: str) -> list[GuidanceBlock]:
    paragraph_parts = [
        paragraph.strip()
        for paragraph in re.split(r"\n{2,}", text)
        if paragraph.strip()
    ]
    return [
        GuidanceBlock(method="guidance_paragraph", text=paragraph)
        for paragraph in paragraph_parts
    ]


def is_guidance_page_artifact_line(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped:
        return True
    if RE_STANDALONE_PAGE_NUMBER.match(stripped):
        return True
    if RE_FOOTNOTE_LINE.match(stripped):
        lower = stripped.lower()
        if "далее" in lower or "сноск" in lower:
            return True
    return False


def is_admissible_guidance_point_match(
    text: str,
    match: re.Match[str],
    *,
    allow_noninitial_sequence: bool,
) -> bool:
    _ = allow_noninitial_sequence
    if match.start() > 0:
        prefix_tail = text[: match.start()].rstrip()
        if prefix_tail.endswith("№"):
            return False

    remainder = text[match.end() :].lstrip()
    if not remainder:
        return False
    first_line = remainder.splitlines()[0].strip()
    if not first_line:
        return False
    if RE_GUIDANCE_POINT_CITATION_PREFIX.match(first_line):
        return False
    return True


__all__ = [
    "GuidanceBlock",
    "GuidancePointMetadata",
    "RE_GUIDANCE_POINT_START",
    "extract_guidance_point_metadata",
    "is_admissible_guidance_point_match",
    "is_guidance_page_artifact_line",
    "normalize_guidance_text",
    "split_guidance_blocks",
]
