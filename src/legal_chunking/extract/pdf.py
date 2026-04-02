"""Deterministic PDF text extraction for OSS chunking flows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from legal_chunking.detect.headings import detect_heading
from legal_chunking.normalize import normalize_extracted_text

_PAGE_NUMBER_LINE_RE = re.compile(r"^\d{1,4}$")
_LIST_MARKER_RE = re.compile(r"^(?:[-*•]|[0-9]+[.)]|[а-яa-z]\))\s+", re.IGNORECASE)
_ROMAN_MARKER_ONLY_RE = re.compile(r"^[IVXLCDM]+\.$")
_ALPHA_MARKER_ONLY_RE = re.compile(r"^[A-Z]\.$")
_TOC_LEADER_RE = re.compile(r"\.{5,}\s*\d+\s*$")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_TERMINAL_PUNCTUATION = (".", "!", "?", ":", ";")
_LEADING_HEADER_MARKERS = (
    "virtual assets regulatory authority",
    "صندوق بريد",
    "سُلطة تنظيم",
    "سلطة تنظيم",
    "سلطة تنظيم الأصول الافتراضية",
    "سُلطة تنظيم الأصول الافتراضية",
    "األصول االفتراضية",
)


@dataclass(slots=True, frozen=True)
class PdfPageText:
    page_number: int
    text: str


def _normalize_line_text(line: str) -> str:
    normalized = (line or "").replace("\xa0", " ")
    normalized = normalized.replace("\u00ad", "").replace("\u2011", "-")
    return re.sub(r"[ \t]+", " ", normalized).strip()


def _find_repeated_page_noise(page_lines: list[list[str]]) -> set[str]:
    counts: dict[str, int] = {}
    for lines in page_lines:
        candidates = [line for line in (*lines[:3], *lines[-3:]) if len(line) >= 40]
        for line in set(candidates):
            counts[line] = counts.get(line, 0) + 1
    return {line for line, count in counts.items() if count >= 3}


def _is_running_header_line(line: str) -> bool:
    lowered = (line or "").strip().lower()
    if not lowered:
        return False
    if "contents" == lowered:
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


def _is_leading_header_fragment(line: str) -> bool:
    stripped = (line or "").strip()
    lowered = stripped.lower()
    if not stripped:
        return False
    return any(marker in lowered for marker in _LEADING_HEADER_MARKERS)


def _trim_leading_header_fragments(lines: list[str]) -> list[str]:
    start = 0
    while start < len(lines) and start < 2 and _is_leading_header_fragment(lines[start]):
        start += 1
    return lines[start:]


def _is_structural_heading_line(line: str, *, profile: str) -> bool:
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


def _is_enumerated_content_line(line: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    return bool(_LIST_MARKER_RE.match(normalized))


def _looks_like_explicit_heading_start(line: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    return lowered.startswith(
        ("part ", "chapter ", "section ", "article ", "schedule ", "annex ", "appendix ")
    )


def _merge_marker_lines(lines: list[str]) -> list[str]:
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


def _looks_like_continuation(line: str, *, profile: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    if _is_enumerated_content_line(normalized) or _is_structural_heading_line(
        normalized,
        profile=profile,
    ):
        return False
    first_char = normalized[0]
    return first_char.islower() or first_char in {'"', "«", "(", "["}


def _append_line(buffer: list[str], line: str, *, profile: str) -> None:
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


def _normalize_page_raw_text(
    raw: str,
    *,
    profile: str,
    repeated_noise: set[str] | None = None,
) -> str:
    raw = (raw or "").replace("\r", "\n")
    lines = [_normalize_line_text(line) for line in raw.split("\n")]
    lines = [
        line
        for line in lines
        if line
        and line not in (repeated_noise or set())
        and not _is_running_header_line(line)
    ]
    lines = _trim_leading_header_fragments(lines)
    if sum(1 for line in lines if _TOC_LEADER_RE.search(line)) >= 2:
        return ""
    lines = _merge_marker_lines(lines)

    paragraphs: list[str] = []
    buffer: list[str] = []

    for line in lines:
        if not line:
            if buffer:
                paragraphs.extend(part for part in buffer if part)
                buffer = []
            continue
        if _PAGE_NUMBER_LINE_RE.match(line):
            continue
        if _TOC_LEADER_RE.search(line):
            continue
        if _is_structural_heading_line(line, profile=profile):
            if buffer:
                paragraphs.extend(part for part in buffer if part)
                buffer = []
            paragraphs.append(line)
            continue
        if _is_enumerated_content_line(line):
            if buffer:
                paragraphs.extend(part for part in buffer if part)
                buffer = []
            paragraphs.append(line)
            continue
        _append_line(buffer, line, profile=profile)

    if buffer:
        paragraphs.extend(part for part in buffer if part)

    return normalize_extracted_text("\n".join(part for part in paragraphs if part))


def extract_pdf_pages(path: str | Path, *, profile: str = "generic") -> list[PdfPageText]:
    """Extract normalized page text from a PDF with deterministic cleanup."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise RuntimeError(
            "PyMuPDF is required for PDF extraction. Install with: pip install legal-chunking[pdf]"
        ) from exc

    document = fitz.open(Path(path))
    pages: list[PdfPageText] = []
    try:
        raw_pages: list[tuple[int, str]] = []
        normalized_line_pages: list[list[str]] = []
        for page_number, page in enumerate(document, start=1):
            raw = (page.get_text("text") or "").strip()
            if not raw:
                continue
            raw_pages.append((page_number, raw))
            normalized_lines = [
                line
                for line in (
                    _normalize_line_text(part) for part in raw.replace("\r", "\n").split("\n")
                )
                if line
            ]
            normalized_line_pages.append(
                normalized_lines
            )
        repeated_noise = _find_repeated_page_noise(normalized_line_pages)
        for page_number, raw in raw_pages:
            normalized = _normalize_page_raw_text(
                raw,
                profile=profile,
                repeated_noise=repeated_noise,
            )
            if not normalized:
                continue
            pages.append(PdfPageText(page_number=page_number, text=normalized))
    finally:
        document.close()
    return pages


def extract_pdf_text(path: str | Path, *, profile: str = "generic") -> str:
    """Extract one normalized text view from a PDF path."""
    pages = extract_pdf_pages(path, profile=profile)
    return "\n\n".join(page.text for page in pages).strip()


__all__ = ["PdfPageText", "extract_pdf_pages", "extract_pdf_text"]
