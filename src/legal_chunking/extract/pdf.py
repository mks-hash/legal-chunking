"""Compatibility facade for staged PDF extraction modules."""

from __future__ import annotations

from .pdf_rules import (
    find_repeated_leading_header_fingerprints as _find_repeated_leading_header_fingerprints,
)
from .pdf_rules import find_repeated_page_noise as _find_repeated_page_noise
from .pdf_runtime import extract_pdf_pages, extract_pdf_text
from .pdf_runtime import normalize_page_raw_text as _normalize_page_raw_text
from .pdf_types import PdfPageText

__all__ = [
    "PdfPageText",
    "_find_repeated_leading_header_fingerprints",
    "_find_repeated_page_noise",
    "_normalize_page_raw_text",
    "extract_pdf_pages",
    "extract_pdf_text",
]
