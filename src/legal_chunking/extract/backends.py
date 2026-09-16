"""Explicit PDF extraction dispatch independent of legal profiles and chunking."""

from __future__ import annotations

import re
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from legal_chunking.errors import PdfDependencyError
from legal_chunking.tracing import TraceCollector, TraceStage

from .models import ExtractedPage

if TYPE_CHECKING:
    import pymupdf


def extract_pages(
    path: str | Path,
    *,
    backend: str = "pymupdf",
    ocr: str = "off",
    ocr_language: str = "eng",
    ocr_dpi: int = 300,
    trace: TraceCollector | None = None,
) -> list[ExtractedPage]:
    if backend not in {"pymupdf", "pymupdf4llm"}:
        raise ValueError(f"Unsupported extraction backend: {backend}")
    if ocr not in {"off", "auto", "force"}:
        raise ValueError(f"Unsupported OCR mode: {ocr}")
    if backend == "pymupdf" and ocr != "off":
        raise ValueError("OCR requires backend='pymupdf4llm'")
    if re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", ocr_language) is None:
        raise ValueError("OCR language must name traineddata languages, for example eng+rus")
    if isinstance(ocr_dpi, bool) or not isinstance(ocr_dpi, int) or not 72 <= ocr_dpi <= 600:
        raise ValueError("OCR dpi must be an integer between 72 and 600")
    try:
        import pymupdf
    except ImportError as exc:
        raise PdfDependencyError(
            "PyMuPDF is required. Install with: pip install 'legal-chunking[pdf]'"
        ) from exc

    if backend == "pymupdf4llm":
        from .pymupdf4llm import extract_layout_pages

        pages = extract_layout_pages(path, ocr=ocr, language=ocr_language, dpi=ocr_dpi, trace=trace)
    else:
        with pymupdf.open(Path(path)) as document:
            pages = [
                ExtractedPage(page_number=number, text=_native_page_text(page))
                for number, page in enumerate(document, start=1)
            ]
    if trace is not None:
        trace.emit(
            TraceStage.EXTRACT,
            "extraction_backend_selected",
            backend=backend,
            backend_version=version(backend),
            pymupdf_version=version("pymupdf"),
            ocr=ocr,
            ocr_engine="tesseract" if ocr != "off" else None,
            ocr_language=ocr_language if ocr != "off" else None,
            ocr_dpi=ocr_dpi if ocr != "off" else None,
            page_count=len(pages),
        )
    return pages


def _native_page_text(page: pymupdf.Page) -> str:
    # Reconstruct native line order while preserving raised numeric glyphs as
    # Unicode superscripts. This is typography evidence, not a dotted-number
    # interpretation; the text engine requires a legal marker for that decision.
    from legal_chunking.manifest import load_asset_json

    digits = load_asset_json("normalization_policy/generic.v1.json")["superscript_digits"]
    raised_digits = str.maketrans("0123456789-", digits + "⁻")
    lines: list[str] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            parts: list[str] = []
            for span in line["spans"]:
                text = span["text"]
                if span["flags"] & 1 and text.strip() and all(c in "0123456789- " for c in text):
                    text = text.translate(raised_digits)
                parts.append(text)
            lines.append("".join(parts))
    return "\n".join(lines)
