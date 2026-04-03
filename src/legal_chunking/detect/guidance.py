"""Guidance/review point block detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

RE_GUIDANCE_POINT_START = re.compile(
    r"(?m)^(?:(?i:пункт)\s+)?(?P<num>\d{1,3})\.\s+(?=[A-ZА-ЯЁ])",
)
RE_GUIDANCE_POINT_CITATION_PREFIX = re.compile(
    r"^(определение\s+судебной\s+коллегии|см\.\s+также)\b",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class GuidanceBlock:
    method: str
    text: str
    point_number: str | None = None


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
    "RE_GUIDANCE_POINT_START",
    "is_admissible_guidance_point_match",
    "split_guidance_blocks",
]
