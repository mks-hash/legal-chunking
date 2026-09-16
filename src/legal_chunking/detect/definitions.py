"""Definition-entry parsing for schedule-like legal text."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TERM_HEADER_RE = re.compile(r"^\s*term\s+definition\s*$", re.IGNORECASE | re.MULTILINE)
_ENTRY_START_RE = re.compile(
    r'(?P<header>"[^"\n]{1,200}"(?:\s+or\s+"[^"\n]{1,200}")*)\s+'
    r"(?P<intro>"
    r"means\b|"
    r"has\s+the\s+meaning\s+ascribed\s+to\s+the\s+term\b|"
    r"has\s+the\s+meaning\s+ascribed\s+to\s+it\s+in\b|"
    r"has\s+the\s+meaning\s+ascribed\s+to\s+it\b|"
    r"has\s+the\s+meaning\s+ascribed\s+to\b"
    r")",
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


@dataclass(slots=True, frozen=True)
class _DefinitionSpan:
    entry: DefinitionEntry
    start: int
    end: int


def _parse_definition_spans(text: str) -> list[_DefinitionSpan]:
    """Recognize metadata while retaining ranges in the original section text."""
    source = text or ""
    spans: list[_DefinitionSpan] = []
    matches = list(_ENTRY_START_RE.finditer(source))
    for index, match in enumerate(matches):
        aliases = [alias.strip() for alias in _QUOTED_ALIAS_RE.findall(match.group("header") or "")]
        term = " / ".join(alias for alias in aliases if alias)
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        segment = source[match.start() : next_start]
        end = match.start() + len(segment.rstrip())
        body = source[match.end("header") : end].strip()
        # A standalone table heading is metadata noise, not permission to erase prose.
        body = _TERM_HEADER_RE.sub("", body)
        body = _ENTRY_TERMINATOR_RE.sub(". ", body).strip()
        if term and body:
            spans.append(_DefinitionSpan(DefinitionEntry(term, body), match.start(), end))
    return spans


def parse_definition_entries(text: str) -> list[DefinitionEntry]:
    """Extract quoted term-definition pairs from a schedule-style block."""
    return [span.entry for span in _parse_definition_spans(text)]


__all__ = ["DefinitionEntry", "parse_definition_entries"]
