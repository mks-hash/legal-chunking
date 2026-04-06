"""Vocabulary-driven context resolution for legal reference normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass

from legal_chunking.numbering_markers import get_numbering_aliases

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё§.]+", re.UNICODE)
_RU_DOC_FAMILY_HINT_RE = re.compile(
    r"(?i)\b(?:крф|гк|апк|гпк|кас|упк|ук|коап|нк|тк|ск)(?:\s+рф)?\b"
)
_CONTEXT_FAMILIES = (
    "article_like",
    "chapter_like",
    "section_like",
    "point_like",
    "subpoint_like",
    "paragraph_like",
    "part_like",
)


@dataclass(slots=True, frozen=True)
class ReferenceContext:
    family: str

    @property
    def is_legal_reference(self) -> bool:
        return self.family != "unknown"


class ReferenceContextResolver:
    """Resolve legal-reference context from profile vocabulary families."""

    def __init__(self, profile: str) -> None:
        self._profile = profile
        self._aliases: dict[str, set[str]] = {
            family: {
                alias.casefold()
                for alias in get_numbering_aliases(profile=profile, families=[family])
                if alias.strip()
            }
            for family in _CONTEXT_FAMILIES
        }

    def detect_context(self, text: str) -> ReferenceContext:
        tokens = {token.casefold() for token in _TOKEN_RE.findall(text or "")}
        for family in _CONTEXT_FAMILIES:
            if tokens & self._aliases[family]:
                return ReferenceContext(family=family)
        if self._profile == "ru" and _RU_DOC_FAMILY_HINT_RE.search(text or ""):
            return ReferenceContext(family="article_like")
        return ReferenceContext(family="unknown")


__all__ = ["ReferenceContext", "ReferenceContextResolver"]
