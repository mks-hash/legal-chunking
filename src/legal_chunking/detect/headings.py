"""Heading detection over asset-backed profile patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from legal_chunking.profiles import resolve_profile

ALLOWED_SECTION_TYPES = {
    "chapter",
    "part",
    "section",
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
    "article": "Article",
    "clause": "Clause",
    "paragraph": "Paragraph",
    "schedule": "Schedule",
}


GUIDANCE_BLOCKED_KINDS = {"article", "clause", "paragraph"}


@dataclass(slots=True)
class HeadingMatch:
    kind: str
    label: str
    article_number: str | None = None
    paragraph_number: str | None = None


@lru_cache(maxsize=32)
def compile_heading_patterns(profile: str) -> list[tuple[str, re.Pattern[str]]]:
    """Compile asset-backed heading patterns for one resolved profile."""
    payload = resolve_profile(profile).heading_patterns
    patterns = payload.get("patterns", [])
    if not isinstance(patterns, list):
        raise ValueError("Heading patterns payload must contain a list in 'patterns'")

    compiled: list[tuple[str, re.Pattern[str]]] = []
    for item in patterns:
        if not isinstance(item, dict):
            raise ValueError("Heading pattern entry must be an object")
        section_type = str(item.get("section_type") or "").strip()
        regex = str(item.get("regex") or "").strip()
        if not section_type or not regex:
            raise ValueError(f"Invalid heading pattern entry: {item}")
        if section_type not in ALLOWED_SECTION_TYPES:
            raise ValueError(f"Unsupported section_type '{section_type}'")
        compiled.append((section_type, re.compile(regex, re.IGNORECASE)))
    return compiled


def _format_label(section_type: str, match: re.Match[str]) -> str:
    num = match.groupdict().get("num") or ""
    title = (match.groupdict().get("title") or "").strip()
    if num:
        prefix = LABEL_PREFIX.get(section_type, section_type.capitalize())
        return f"{prefix} {num}" + (f". {title}" if title else "")
    return match.group(0).strip()


def _has_explicit_numeric_heading_marker(line: str, num_token: str) -> bool:
    heading = (line or "").strip()
    normalized_num = (num_token or "").strip()
    if not heading or not normalized_num:
        return False
    if "." in normalized_num:
        return True

    suffix = heading[len(normalized_num) :].lstrip()
    return bool(suffix[:1] in {".", ")"})


def _is_admissible_numeric_heading(
    line: str,
    num_token: str,
    title: str,
    *,
    chunk_policy: str,
) -> bool:
    normalized_num = (num_token or "").strip()
    tail = (title or "").strip()
    if not normalized_num or not tail:
        return False
    if not _has_explicit_numeric_heading_marker(line, normalized_num):
        return False
    if len(tail) > 120:
        return False
    words = tail.split()
    if len(words) > 14:
        return False
    punctuation_hits = len(re.findall(r"[.!?;:]", tail))
    if punctuation_hits > 1:
        return False
    if tail[:1].islower():
        return False
    if chunk_policy in {"guidance", "case_law"} and len(words) > 10:
        return False
    return True


def _is_admissible_symbolic_heading(title: str, *, chunk_policy: str) -> bool:
    tail = (title or "").strip()
    if not tail:
        return False
    if len(tail) > 120:
        return False
    words = tail.split()
    if len(words) > 14:
        return False
    punctuation_hits = len(re.findall(r"[.!?;:]", tail))
    if punctuation_hits > 1:
        return False
    if tail[:1].islower():
        return False
    if chunk_policy in {"guidance", "case_law"} and len(words) > 10:
        return False
    return True


def detect_heading(
    line: str,
    *,
    profile: str = "generic",
    chunk_policy: str = "default",
) -> HeadingMatch | None:
    """Detect one canonical heading from a line of normalized text."""
    heading = (line or "").strip()
    if not heading:
        return None

    for section_type, pattern in compile_heading_patterns(profile):
        match = pattern.match(heading)
        if not match:
            continue

        if section_type == "numeric_heading":
            raw_num = match.groupdict().get("num") or ""
            tail = match.groupdict().get("title") or ""
            if not _is_admissible_numeric_heading(
                heading,
                raw_num,
                tail,
                chunk_policy=chunk_policy,
            ):
                return None
            num = raw_num.rstrip(".")
            label = f"Section {num}" + (f". {tail}" if tail else "")
            depth = num.count(".")
            if depth == 0:
                return HeadingMatch(kind="section", label=label)
            if chunk_policy == "guidance":
                return None
            if depth == 1:
                return HeadingMatch(kind="article", label=label, article_number=num)
            return HeadingMatch(kind="clause", label=label, paragraph_number=num)

        if section_type == "roman_heading":
            num = match.groupdict().get("num") or ""
            tail = match.groupdict().get("title") or ""
            if not _is_admissible_symbolic_heading(tail, chunk_policy=chunk_policy):
                return None
            label = f"Section {num}" + (f". {tail}" if tail else "")
            return HeadingMatch(kind="section", label=label)

        if chunk_policy == "guidance" and section_type in GUIDANCE_BLOCKED_KINDS:
            return None

        label = _format_label(section_type, match)
        if section_type == "schedule":
            return HeadingMatch(kind="other", label=label)
        if section_type == "article":
            return HeadingMatch(
                kind="article",
                label=label,
                article_number=match.groupdict().get("num"),
            )
        if section_type in {"clause", "paragraph"}:
            return HeadingMatch(
                kind=section_type,
                label=label,
                paragraph_number=match.groupdict().get("num"),
            )
        return HeadingMatch(kind=section_type, label=label)

    return None
