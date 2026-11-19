"""High-level library API."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable, Sequence
from pathlib import Path

from legal_chunking.chunk import build_chunks
from legal_chunking.detect.guidance_normalization import (
    _normalize_guidance_view,
    normalize_guidance_text,
)
from legal_chunking.detect.sections import assemble_sections
from legal_chunking.extract.models import ExtractedPage
from legal_chunking.extract.pdf import extract_pdf_pages, extract_pdf_text
from legal_chunking.legal_normalization import (
    _normalize_structural_numbering_view,
    normalize_structural_numbering,
)
from legal_chunking.models import Document
from legal_chunking.normalize import _normalize_extracted_view, normalize_extracted_text
from legal_chunking.profiles import (
    ResolvedProfile,
    resolve_profile,
    select_chunk_fallback,
    select_chunk_policy,
)
from legal_chunking.text_mapping import _TextView
from legal_chunking.tracing import TraceCollector, TraceStage


def chunk_text(
    text: str,
    profile: str = "generic",
    source_name: str = "<memory>",
    doc_kind: str | None = None,
    trace: bool = False,
) -> Document:
    """Return deterministic sections and policy-aware chunks for normalized text input."""
    resolved_profile = resolve_profile(profile)
    return _chunk_normalized_text(
        text=text,
        resolved_profile=resolved_profile,
        source_name=source_name,
        doc_kind=doc_kind,
        trace=trace,
        trace_collector=None,
    )


def chunk_pages(
    pages: Sequence[ExtractedPage],
    profile: str = "generic",
    source_name: str = "<memory>",
    doc_kind: str | None = None,
    trace: bool = False,
) -> Document:
    """Return deterministic sections and policy-aware chunks with page provenance."""
    resolved_profile = resolve_profile(profile)
    return _chunk_pages(
        pages=pages,
        resolved_profile=resolved_profile,
        source_name=source_name,
        doc_kind=doc_kind,
        trace=trace,
        trace_collector=None,
    )


def _validate_extracted_pages(pages: Sequence[ExtractedPage]) -> list[ExtractedPage]:
    validated: list[ExtractedPage] = []
    for page in pages:
        if not isinstance(page, ExtractedPage):
            raise TypeError(f"Expected ExtractedPage, got {type(page).__name__}")
        if isinstance(page.page_number, bool) or not isinstance(page.page_number, int):
            raise ValueError(f"Invalid page_number: {page.page_number!r}")
        if page.page_number < 1:
            raise ValueError(f"page_number must be >= 1, got {page.page_number}")
        if page.text and page.text.strip():
            validated.append(page)
    return validated


def _chunk_pages(
    *,
    pages: Sequence[ExtractedPage],
    resolved_profile: ResolvedProfile,
    source_name: str,
    doc_kind: str | None,
    trace: bool,
    trace_collector: TraceCollector | None,
) -> Document:
    non_empty_pages = _validate_extracted_pages(pages)
    chunk_policy = select_chunk_policy(resolved_profile.chunking_policy, doc_kind=doc_kind)
    if not non_empty_pages:
        return _chunk_prepared_document(
            normalized_document="",
            resolved_profile=resolved_profile,
            chunk_policy=chunk_policy,
            source_name=source_name,
            doc_kind=doc_kind,
            trace=trace,
            trace_collector=trace_collector,
            page_for_offset=None,
        )

    raw_parts: list[str] = []
    page_starts: list[int] = []
    page_numbers: list[int] = []
    cursor = 0
    for index, page in enumerate(non_empty_pages):
        if index > 0:
            raw_parts.append("\n\n")
            cursor += 2
        page_starts.append(cursor)
        page_numbers.append(page.page_number)
        raw_parts.append(page.text)
        cursor += len(page.text)
    raw_joined = "".join(raw_parts)

    view = _normalize_extracted_view(_TextView.from_source(raw_joined, track=True))
    view = _normalize_structural_numbering_view(view, profile=resolved_profile.code)
    if chunk_policy == "guidance":
        view = _normalize_guidance_view(view, profile=resolved_profile.code)

    def page_for_offset(offset: int) -> int | None:
        if view.origins is None or not view.origins.starts:
            return None
        clamped = min(max(0, offset), len(view.origins.starts) - 1)
        raw_offset = view.origins.starts[clamped]
        idx = bisect_right(page_starts, raw_offset) - 1
        return page_numbers[max(0, idx)]

    return _chunk_prepared_document(
        normalized_document=view.text,
        resolved_profile=resolved_profile,
        chunk_policy=chunk_policy,
        source_name=source_name,
        doc_kind=doc_kind,
        trace=trace,
        trace_collector=trace_collector,
        page_for_offset=page_for_offset,
    )


def _chunk_normalized_text(
    *,
    text: str,
    resolved_profile: ResolvedProfile,
    source_name: str,
    doc_kind: str | None,
    trace: bool,
    trace_collector: TraceCollector | None,
) -> Document:
    chunk_policy = select_chunk_policy(resolved_profile.chunking_policy, doc_kind=doc_kind)
    normalized_document = normalize_structural_numbering(
        normalize_extracted_text(text), profile=resolved_profile.code
    )
    if chunk_policy == "guidance":
        normalized_document = normalize_guidance_text(
            normalized_document, profile=resolved_profile.code
        )
    return _chunk_prepared_document(
        normalized_document=normalized_document,
        resolved_profile=resolved_profile,
        chunk_policy=chunk_policy,
        source_name=source_name,
        doc_kind=doc_kind,
        trace=trace,
        trace_collector=trace_collector,
        page_for_offset=None,
    )


def _chunk_prepared_document(
    *,
    normalized_document: str,
    resolved_profile: ResolvedProfile,
    chunk_policy: str,
    source_name: str,
    doc_kind: str | None,
    trace: bool,
    trace_collector: TraceCollector | None,
    page_for_offset: Callable[[int], int | None] | None,
) -> Document:
    fallback = select_chunk_fallback(resolved_profile.chunking_policy)
    if trace:
        trace_collector = trace_collector or TraceCollector()
    else:
        trace_collector = None
    if trace_collector is not None:
        trace_collector.emit(
            TraceStage.CHUNK,
            "chunk_policy_selected",
            profile=resolved_profile.code,
            doc_kind=doc_kind,
            policy=chunk_policy,
        )
        trace_collector.emit(
            TraceStage.NORMALIZE,
            "document_normalized",
            source_name=source_name,
            char_length=len(normalized_document),
        )
    sections = assemble_sections(
        normalized_document,
        profile=resolved_profile.code,
        source_name=source_name,
        chunk_policy=chunk_policy,
        doc_kind=doc_kind,
        trace=trace_collector,
    )
    chunks = build_chunks(
        sections,
        source_name=source_name,
        resolved_profile=resolved_profile,
        chunk_policy=chunk_policy,
        fallback=fallback,
        trace=trace_collector,
        normalized_text=normalized_document,
        page_for_offset=page_for_offset,
    )
    return Document(
        source_name=source_name,
        profile=resolved_profile.code,
        language=resolved_profile.language,
        text=normalized_document,
        chunk_policy=chunk_policy,
        sections=sections,
        chunks=chunks,
        trace=trace_collector.to_report() if trace_collector is not None else None,
    )


def chunk_pdf(
    path: str | Path,
    profile: str = "generic",
    doc_kind: str | None = None,
    trace: bool = False,
    *,
    backend: str = "pymupdf",
    ocr: str = "off",
    ocr_language: str = "eng",
    ocr_dpi: int = 300,
) -> Document:
    """Extract normalized PDF pages and pass them through the chunking pipeline."""
    source = Path(path)
    resolved_profile = resolve_profile(profile)
    trace_collector = TraceCollector() if trace else None
    pages = extract_pdf_pages(
        source,
        profile=resolved_profile,
        trace=trace_collector,
        backend=backend,
        ocr=ocr,
        ocr_language=ocr_language,
        ocr_dpi=ocr_dpi,
    )
    return _chunk_pages(
        pages=pages,
        resolved_profile=resolved_profile,
        source_name=source.name,
        doc_kind=doc_kind,
        trace=trace,
        trace_collector=trace_collector,
    )


def extract_pdf_text_with_trace(
    source: Path,
    *,
    resolved_profile: ResolvedProfile,
    trace_collector: TraceCollector | None,
    backend: str = "pymupdf",
    ocr: str = "off",
    ocr_language: str = "eng",
    ocr_dpi: int = 300,
) -> str:
    return extract_pdf_text(
        source,
        profile=resolved_profile,
        trace=trace_collector,
        backend=backend,
        ocr=ocr,
        ocr_language=ocr_language,
        ocr_dpi=ocr_dpi,
    )
