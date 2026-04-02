"""Definition-entry parsing for schedule-like legal text."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TERM_HEADER_RE = re.compile(r"^\s*term\s+definition\s*$", re.IGNORECASE | re.MULTILINE)
_QUOTED_TERM_RE = re.compile(
    r'"(?P<term>[^"\n]{1,200})"\s*(?P<body>.*?)(?=(?:"[^"\n]{1,200}"\s)|\Z)',
    re.DOTALL,
)


@dataclass(slots=True, frozen=True)
class DefinitionEntry:
    term: str
    definition: str


def parse_definition_entries(text: str) -> list[DefinitionEntry]:
    """Extract quoted term-definition pairs from a schedule-style block."""
    normalized = (text or "").strip()
    if not normalized:
        return []
    normalized = _TERM_HEADER_RE.sub("", normalized)
    entries: list[DefinitionEntry] = []
    for match in _QUOTED_TERM_RE.finditer(normalized):
        term = (match.group("term") or "").strip()
        body = (match.group("body") or "").strip()
        if not term or not body:
            continue
        entries.append(DefinitionEntry(term=term, definition=body))
    return entries


__all__ = ["DefinitionEntry", "parse_definition_entries"]
