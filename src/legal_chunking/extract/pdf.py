"""Deterministic PDF text extraction for OSS chunking flows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from legal_chunking.detect.headings import detect_heading
from legal_chunking.normalize import normalize_extracted_text

_PAGE_NUMBER_LINE_RE = re.compile(r"^\d{1,4}$")
_LIST_MARKER_RE = re.compile(r"^(?:[-*•]|[0-9]+[.)]|[а-яa-z]\))\s+", re.IGNORECASE)
_TERMINAL_PUNCTUATION = (".", "!", "?", ":", ";")


@dataclass(slots=True, frozen=True)
class PdfPageText:
    page_number: int
    text: str


def _normalize_line_text(line: str) -> str:
    normalized = (line or "").replace("\xa0", " ")
    normalized = normalized.replace("\u00ad", "").replace("\u2011", "-")
    return re.sub(r"[ \t]+", " ", normalized).strip()


def _is_heading_like_line(line: str, *, profile: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    if detect_heading(normalized, profile=profile) is not None:
        return True
    if _LIST_MARKER_RE.match(normalized):
        return True
    if len(normalized) > 120:
        return False
    letters = [char for char in normalized if char.isalpha()]
    if not letters:
        return False
    uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    return uppercase_ratio >= 0.85


def _looks_like_continuation(line: str, *, profile: str) -> bool:
    normalized = (line or "").strip()
    if not normalized:
        return False
    if _LIST_MARKER_RE.match(normalized) or _is_heading_like_line(normalized, profile=profile):
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


def _normalize_page_raw_text(raw: str, *, profile: str) -> str:
    raw = (raw or "").replace("\r", "\n")
    lines = [_normalize_line_text(line) for line in raw.split("\n")]

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
        if _is_heading_like_line(line, profile=profile):
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
    document = fitz.open(Path(path))
    pages: list[PdfPageText] = []
    try:
        for page_number, page in enumerate(document, start=1):
            raw = (page.get_text("text") or "").strip()
            if not raw:
                continue
            normalized = _normalize_page_raw_text(raw, profile=profile)
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
