"""Typed heading detection models and constants."""

from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_SECTION_TYPES = {
    "chapter",
    "part",
    "section",
    "rule",
    "alpha_heading",
    "article",
    "clause",
    "paragraph",
    "schedule",
    "roman_heading",
    "numeric_heading",
}

LABEL_PREFIX = {
    "chapter": "Chapter",
    "part": "Part",
    "section": "Section",
    "rule": "Rule",
    "article": "Article",
    "clause": "Clause",
    "paragraph": "Paragraph",
    "schedule": "Schedule",
}

GUIDANCE_BLOCKED_KINDS = {"article", "clause", "paragraph"}
PREFIXED_EXPLICIT_HEADING_RE = re.compile(
    r"^(?P<prefix>[IVXLCDM]+)\.\s+(?P<rest>(part|chapter|section|schedule)\b.+)$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class HeadingMatch:
    kind: str
    label: str
    article_number: str | None = None
    paragraph_number: str | None = None


__all__ = [
    "ALLOWED_SECTION_TYPES",
    "GUIDANCE_BLOCKED_KINDS",
    "LABEL_PREFIX",
    "PREFIXED_EXPLICIT_HEADING_RE",
    "HeadingMatch",
]
