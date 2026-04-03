"""Definition-entry parsing for schedule-like legal text."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TERM_HEADER_RE = re.compile(r"^\s*term\s+definition\s*$", re.IGNORECASE | re.MULTILINE)
_TERM_HEADER_INLINE_RE = re.compile(r"\bterm\s+definition\b", re.IGNORECASE)
_ENTRY_START_RE = re.compile(
    r'(?P<header>"[^"\n]{1,200}"(?:\s+or\s+"[^"\n]{1,200}")*)\s+'
    r'(?P<intro>'
    r'means\b|'
    r'has\s+the\s+meaning\s+ascribed\s+to\s+the\s+term\b|'
    r'has\s+the\s+meaning\s+ascribed\s+to\s+it\s+in\b|'
    r'has\s+the\s+meaning\s+ascribed\s+to\s+it\b|'
    r'has\s+the\s+meaning\s+ascribed\s+to\b'
    r')',
    re.IGNORECASE,
)
_QUOTED_ALIAS_RE = re.compile(r'"([^"\n]{1,200})"')
_ENTRY_TERMINATOR_RE = re.compile(
    r"(?<!\b[A-Z])[.](?:\s+|\n+)(?=\")",
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
    normalized = _TERM_HEADER_INLINE_RE.sub("", normalized)
    entries: list[DefinitionEntry] = []
    matches = list(_ENTRY_START_RE.finditer(normalized))
    for index, match in enumerate(matches):
        aliases = [alias.strip() for alias in _QUOTED_ALIAS_RE.findall(match.group("header") or "")]
        term = " / ".join(alias for alias in aliases if alias)
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        body = normalized[match.end("header") : next_start].strip()
        body = _ENTRY_TERMINATOR_RE.sub(". ", body).strip()
        if not term or not body:
            continue
        entries.append(DefinitionEntry(term=term, definition=body))
    return entries


__all__ = ["DefinitionEntry", "parse_definition_entries"]
