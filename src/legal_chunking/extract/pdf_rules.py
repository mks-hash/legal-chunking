"""Low-level PDF line rules and normalization helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from legal_chunking.detect.headings import detect_heading

if TYPE_CHECKING:
    from legal_chunking.profiles import ResolvedProfile

_PAGE_NUMBER_LINE_RE = re.compile(r"^\d{1,4}$")
_LIST_MARKER_RE = re.compile(r"^(?:[-*•]|[0-9]+[.)]|[а-яa-z]\))\s+", re.IGNORECASE)
_ROMAN_MARKER_ONLY_RE = re.compile(r"^[IVXLCDM]+\.$")
_ALPHA_MARKER_ONLY_RE = re.compile(r"^[A-Z]\.$")
_TOC_LEADER_RE = re.compile(r"\.{5,}\s*\d+\s*$")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_US_RUNNING_RULE_HEADER_RE = re.compile(r"^Rule\s+\d+(?:\.\d+)?$", re.IGNORECASE)
_TERMINAL_PUNCTUATION = (".", "!", "?", ":", ";")


def normalize_line_text(line: str) -> str:
    normalized = (line or "").replace("\xa0", " ")
    normalized = normalized.replace("\u00ad", "").replace("\u2011", "-")
    return re.sub(r"[ \t]+", " ", normalized).strip()


def find_repeated_page_noise(page_lines: list[list[str]]) -> set[str]:
    counts: dict[str, int] = {}
    for lines in page_lines:
        candidates = [
            line for line in (*lines[:8], *lines[-4:]) if _is_repeated_noise_candidate(line)
        ]
        for line in set(candidates):
            counts[line] = counts.get(line, 0) + 1
    return {line for line, count in counts.items() if count >= 3}


def find_repeated_leading_header_fingerprints(page_lines: list[list[str]]) -> set[str]:
    counts: dict[str, int] = {}
    for lines in page_lines:
        candidates = [_header_fragment_fingerprint(line) for line in lines[:8]]
        for fingerprint in set(candidate for candidate in candidates if candidate):
            counts[fingerprint] = counts.get(fingerprint, 0) + 1
    return {fingerprint for fingerprint, count in counts.items() if count >= 3}


def is_profile_specific_noise_line(line: str, *, resolved_profile: ResolvedProfile) -> bool:
    stripped = (line or "").strip()
    lowered = stripped.lower()
    if not stripped:
        return False
    runtime = resolved_profile.runtime.pdf
    if lowered in {value.casefold() for value in runtime.drop_line_equals}:
        return True
    for pattern in runtime.drop_line_regexes:
        if re.match(pattern, stripped, re.IGNORECASE):
            return True
    return False


def is_running_header_line(line: str) -> bool:
    return _is_running_header_line(line)


def trim_leading_header_fragments(
    lines: list[str],
    *,
    repeated_noise: set[str] | None = None,
    repeated_fingerprints: set[str] | None = None,
) -> list[str]:
    start = 0
    if lines and len(lines[0].strip()) == 1 and lines[0].strip().isalpha():
        next_line = lines[1] if len(lines) > 1 else ""
        if _is_leading_header_fragment(
            next_line,
            repeated_noise=repeated_noise,
            repeated_fingerprints=repeated_fingerprints,
        ):
            start = 1
    while start < len(lines) and start < 4 and _is_leading_header_fragment(
        lines[start],
        repeated_noise=repeated_noise,
        repeated_fingerprints=repeated_fingerprints,
    ):
        start += 1
    return lines[start:]


def is_structural_heading_line(line: str, *, profile: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    if detect_heading(normalized, profile=profile) is not None:
        return True
    if len(normalized) > 120:
        return False
    letters = [char for char in normalized if char.isalpha()]
    if not letters:
        return False
    uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    return uppercase_ratio >= 0.85


def is_enumerated_content_line(line: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    return bool(_LIST_MARKER_RE.match(normalized))


def merge_marker_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        if _ROMAN_MARKER_ONLY_RE.match(line) and _looks_like_explicit_heading_start(next_line):
            merged.append(next_line)
            idx += 2
            continue
        if _ALPHA_MARKER_ONLY_RE.match(line) and next_line:
            merged.append(f"{line} {next_line}")
            idx += 2
            continue
        merged.append(line)
        idx += 1
    return merged


def append_line(buffer: list[str], line: str, *, profile: str) -> None:
    if not buffer:
        buffer.append(line)
        return

    previous = buffer[-1]
    if previous.endswith("-") and line[:1].islower():
        buffer[-1] = f"{previous[:-1]}{line}"
        return

    if previous.endswith(_TERMINAL_PUNCTUATION) and not _looks_like_continuation(
        line,
        profile=profile,
    ):
        buffer.append(line)
        return

    buffer[-1] = f"{previous} {line}"


def join_wrapped_line(previous: str, current: str) -> str:
    if previous.endswith("-"):
        return f"{previous[:-1]}{current}"
    return f"{previous} {current}"


def looks_like_heading_continuation(
    previous: str,
    current: str,
    *,
    resolved_profile: ResolvedProfile,
) -> bool:
    if not previous or not current:
        return False
    if _PAGE_NUMBER_LINE_RE.match(current):
        return False
    if _TOC_LEADER_RE.search(current):
        return False
    if is_profile_specific_noise_line(current, resolved_profile=resolved_profile):
        return False
    if is_structural_heading_line(current, profile=resolved_profile.code):
        return False
    if is_enumerated_content_line(current):
        return False
    if previous.endswith("-"):
        return True
    if previous.endswith(_TERMINAL_PUNCTUATION):
        return False
    return current[:1].islower()


def trim_us_running_rule_header(lines: list[str]) -> list[str]:
    if len(lines) < 2:
        return lines
    start = 0
    while start < len(lines) and _PAGE_NUMBER_LINE_RE.match(lines[start].strip()):
        start += 1
    while start < len(lines) and lines[start].strip().upper() == "FEDERAL RULES OF CIVIL PROCEDURE":
        start += 1
    if start >= len(lines):
        return lines

    first = lines[start].strip()
    second = lines[start + 1].strip() if start + 1 < len(lines) else ""
    if not _US_RUNNING_RULE_HEADER_RE.match(first):
        return lines[start:]
    if not second:
        return lines[start + 1 :]
    if second[:1] in {"(", "[", '"', "'"}:
        return lines[start + 1 :]
    if second[:1].islower():
        return lines[start + 1 :]
    if second[:1].isdigit():
        return lines[start + 1 :]
    return lines[start:]


def is_page_number_line(line: str) -> bool:
    return bool(_PAGE_NUMBER_LINE_RE.match((line or "").strip()))


def has_toc_leader(line: str) -> bool:
    return bool(_TOC_LEADER_RE.search((line or "").strip()))


def _is_repeated_noise_candidate(line: str) -> bool:
    stripped = (line or "").strip()
    if len(stripped) == 1 and stripped.isalpha():
        return True
    if len(stripped) < 8:
        return False
    if _PAGE_NUMBER_LINE_RE.match(stripped):
        return False
    if _LIST_MARKER_RE.match(stripped):
        return False
    if _TOC_LEADER_RE.search(stripped):
        return False
    return True


def _contains_arabic(text: str) -> bool:
    return any("\u0600" <= char <= "\u06ff" for char in text)


def _normalize_header_fragment_text(line: str) -> str:
    normalized = unicodedata.normalize("NFKC", (line or "").strip())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[ \t]+", " ", normalized).strip()
    if re.match(r"^[A-Za-z]\s+", normalized):
        candidate = normalized[2:].strip()
        if candidate and _contains_arabic(candidate):
            normalized = candidate
    return normalized


def _header_fragment_fingerprint(line: str) -> str:
    normalized = _normalize_header_fragment_text(line)
    if len(normalized) < 4:
        return ""
    if _PAGE_NUMBER_LINE_RE.match(normalized):
        return ""
    return normalized.lower()


def _is_running_header_line(line: str) -> bool:
    lowered = (line or "").strip().lower()
    if not lowered:
        return False
    if lowered == "contents":
        return True
    if "صندوق بريد" in lowered:
        return True
    if "العربية المتحدة" in lowered:
        return True
    if _EMAIL_RE.search(lowered):
        return True
    if "po box" in lowered and "authority" in lowered:
        return True
    return False


def _is_leading_header_fragment(
    line: str,
    *,
    repeated_noise: set[str] | None = None,
    repeated_fingerprints: set[str] | None = None,
) -> bool:
    stripped = (line or "").strip()
    if not stripped:
        return False
    if stripped in (repeated_noise or set()):
        return True
    fingerprint = _header_fragment_fingerprint(stripped)
    return bool(fingerprint and fingerprint in (repeated_fingerprints or set()))


def _looks_like_explicit_heading_start(line: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    return lowered.startswith(
        ("part ", "chapter ", "section ", "article ", "schedule ", "annex ", "appendix ")
    )


def _looks_like_continuation(line: str, *, profile: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    if is_enumerated_content_line(normalized) or is_structural_heading_line(
        normalized,
        profile=profile,
    ):
        return False
    first_char = normalized[0]
    return first_char.islower() or first_char in {'"', "«", "(", "["}


__all__ = [
    "append_line",
    "find_repeated_leading_header_fingerprints",
    "find_repeated_page_noise",
    "has_toc_leader",
    "is_enumerated_content_line",
    "is_page_number_line",
    "is_profile_specific_noise_line",
    "is_running_header_line",
    "is_structural_heading_line",
    "join_wrapped_line",
    "looks_like_heading_continuation",
    "merge_marker_lines",
    "normalize_line_text",
    "trim_leading_header_fragments",
    "trim_us_running_rule_header",
]
