"""Guidance/review point block detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .guidance_policy import guidance_policy


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
    profile: str = "generic",
) -> list[GuidanceBlock]:
    stripped = (text or "").strip()
    if not stripped:
        return []

    policy = guidance_policy(profile)
    body_start = policy.body_start.search(stripped)
    raw_matches = [
        m
        for m in policy.point_start.finditer(stripped)
        if body_start is None or m.start() >= body_start.end()
    ]
    matches: list[re.Match[str]] = []
    for match in raw_matches:
        if is_admissible_guidance_point_match(
            stripped,
            match,
            allow_noninitial_sequence=allow_noninitial_sequence,
            profile=profile,
        ):
            number = int(match.group("num"))
            if matches:
                previous = int(matches[-1].group("num"))
                if number <= previous or number - previous > policy.max_forward_gap:
                    continue
                if number > previous + 1 and any(
                    int(later.group("num")) == previous + 1
                    for later in raw_matches
                    if later.start() > match.start()
                ):
                    continue
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
    return [GuidanceBlock(method="guidance_paragraph", text=text)]


def is_admissible_guidance_point_match(
    text: str,
    match: re.Match[str],
    *,
    allow_noninitial_sequence: bool,
    profile: str = "generic",
) -> bool:
    policy = guidance_policy(profile)
    if match.start() > 0:
        prefix_tail = text[: match.start()].rstrip()
        if policy.excluded_prefix.search(prefix_tail):
            return False

    remainder = text[match.end() :].lstrip()
    if not remainder:
        return False
    first_line = remainder.splitlines()[0].strip()
    if not first_line:
        return False
    if policy.citation_prefix.match(first_line):
        return False
    return True


__all__ = [
    "GuidanceBlock",
    "is_admissible_guidance_point_match",
    "split_guidance_blocks",
]
