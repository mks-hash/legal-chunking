"""Rulebook-style block detection for structured statute chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass

_RULE_START_RE = re.compile(r"^(?P<num>\d+)\.(?:\s+(?P<rest>.*))?$")


@dataclass(slots=True, frozen=True)
class RuleBlock:
    number: str
    text: str


def split_rulebook_rule_blocks(text: str) -> list[RuleBlock]:
    """Split one section body into numbered rule blocks when the pattern is clear."""
    raw_lines = [line.strip() for line in (text or "").splitlines()]
    lines = [line for line in raw_lines if line]
    if len(lines) < 3:
        return []

    heading_index = 1 if _looks_like_section_heading(lines[0]) else 0
    starts: list[tuple[int, str, str]] = []
    for idx in range(heading_index, len(lines)):
        match = _RULE_START_RE.match(lines[idx])
        if not match:
            continue
        starts.append((idx, match.group("num"), (match.group("rest") or "").strip()))

    if len(starts) < 2:
        return []
    if starts[0][1] != "1":
        return []

    numbers = [int(num) for _, num, _ in starts]
    if numbers != sorted(numbers) or len(set(numbers)) != len(numbers):
        return []
    if any(
        current - previous != 1 for previous, current in zip(numbers, numbers[1:], strict=False)
    ):
        return []

    intro_lines = lines[heading_index : starts[0][0]]
    blocks: list[RuleBlock] = []
    for block_index, (start_idx, number, inline_rest) in enumerate(starts):
        end_idx = starts[block_index + 1][0] if block_index + 1 < len(starts) else len(lines)
        body_lines = lines[start_idx + 1 : end_idx]
        content_lines: list[str] = []
        if block_index == 0 and intro_lines:
            content_lines.extend(intro_lines)
        if inline_rest:
            content_lines.insert(0, inline_rest)
        content_lines.extend(body_lines)
        body = "\n".join(part for part in content_lines if part).strip()
        if not body:
            continue
        blocks.append(RuleBlock(number=number, text=body))
    return blocks if len(blocks) >= 2 else []


def _looks_like_section_heading(line: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    return bool(re.match(r"^[A-Z]\.\s+", normalized))


__all__ = ["RuleBlock", "split_rulebook_rule_blocks"]
