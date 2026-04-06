"""PDF extraction runtime orchestration over staged line rules."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from legal_chunking.errors import PdfDependencyError
from legal_chunking.normalize import normalize_extracted_text
from legal_chunking.profiles import resolve_profile
from legal_chunking.tracing import TraceCollector, TraceStage

from .pdf_candidates import (
    EnumeratedContentCandidate,
    PdfLineCandidate,
    StructuralHeadingCandidate,
    TocLeaderCandidate,
)
from .pdf_classify import classify_pdf_line
from .pdf_rules import (
    append_line,
    find_repeated_leading_header_fingerprints,
    find_repeated_page_noise,
    is_profile_specific_noise_line,
    is_structural_heading_line,
    join_wrapped_line,
    looks_like_heading_continuation,
    merge_marker_lines,
    normalize_line_text,
    trim_leading_header_fragments,
    trim_us_running_rule_header,
)
from .pdf_state import PdfParserState, decide_pdf_line
from .pdf_types import PdfPageText

if TYPE_CHECKING:
    from legal_chunking.profiles import ResolvedProfile

_US_RULES_BODY_START_RE = re.compile(
    r"RULES OF CIVIL PROCEDURE\s+FOR THE\s+UNITED STATES DISTRICT COURTS",
    re.IGNORECASE,
)
_US_TOC_MARKER_RE = re.compile(r"\bTABLE OF CONTENTS\b", re.IGNORECASE)


def normalize_page_raw_text(
    raw: str,
    *,
    profile: str | ResolvedProfile,
    repeated_noise: set[str] | None = None,
    repeated_fingerprints: set[str] | None = None,
    trace: TraceCollector | None = None,
) -> str:
    resolved_profile = coerce_resolved_profile(profile)
    raw = (raw or "").replace("\r", "\n")
    lines = [normalize_line_text(line) for line in raw.split("\n")]
    lines = [
        line
        for line in lines
        if line
        and line not in (repeated_noise or set())
        and not is_profile_specific_noise_line(line, resolved_profile=resolved_profile)
    ]
    lines = trim_leading_header_fragments(
        lines,
        repeated_noise=repeated_noise,
        repeated_fingerprints=repeated_fingerprints,
    )
    if resolved_profile.runtime.pdf.trim_running_rule_headers:
        lines = trim_us_running_rule_header(lines)
    classified_lines = _classify_lines(lines, resolved_profile=resolved_profile)
    if trace is not None:
        for candidate in classified_lines:
            trace.emit(
                TraceStage.EXTRACT,
                "pdf_line_classified",
                **_candidate_trace_payload(candidate),
            )
    toc_candidates = [
        candidate
        for candidate in classified_lines
        if isinstance(candidate, TocLeaderCandidate) and candidate.target_page is not None
    ]
    if len(toc_candidates) >= 2:
        return ""
    lines = merge_marker_lines([item.text for item in classified_lines if not item.should_drop])
    if resolved_profile.runtime.pdf.merge_wrapped_headings:
        lines = _merge_wrapped_heading_lines(lines, resolved_profile=resolved_profile)
    refined_candidates = _classify_lines(lines, resolved_profile=resolved_profile)

    paragraphs: list[str] = []
    buffer: list[str] = []
    state = PdfParserState.FRONT_MATTER
    for candidate in refined_candidates:
        if not candidate.text:
            if buffer:
                paragraphs.extend(part for part in buffer if part)
                buffer = []
            continue
        previous_state = state
        decision = decide_pdf_line(candidate, state=state)
        state = decision.state
        if trace is not None:
            trace.emit(
                TraceStage.EXTRACT,
                "pdf_line_decided",
                state_from=previous_state,
                state_to=decision.state,
                keep=decision.keep,
                **_candidate_trace_payload(candidate),
            )
        if not decision.keep:
            continue
        if isinstance(candidate, StructuralHeadingCandidate):
            if buffer:
                paragraphs.extend(part for part in buffer if part)
                buffer = []
            paragraphs.append(candidate.text)
            continue
        if isinstance(candidate, EnumeratedContentCandidate):
            if buffer:
                paragraphs.extend(part for part in buffer if part)
                buffer = []
            paragraphs.append(candidate.text)
            continue
        append_line(buffer, candidate.text, profile=resolved_profile.code)

    if buffer:
        paragraphs.extend(part for part in buffer if part)
    return normalize_extracted_text("\n".join(part for part in paragraphs if part))


def extract_pdf_pages(
    path: str | Path,
    *,
    profile: str | ResolvedProfile = "generic",
    trace: TraceCollector | None = None,
) -> list[PdfPageText]:
    """Extract normalized page text from a PDF with deterministic cleanup."""
    resolved_profile = coerce_resolved_profile(profile)
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise PdfDependencyError(
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
            normalized_line_pages.append(
                [
                    line
                    for line in (
                        normalize_line_text(part) for part in raw.replace("\r", "\n").split("\n")
                    )
                    if line
                ]
            )

        repeated_noise = find_repeated_page_noise(normalized_line_pages)
        repeated_header_fingerprints = find_repeated_leading_header_fingerprints(
            normalized_line_pages
        )
        for page_number, raw in raw_pages:
            normalized = normalize_page_raw_text(
                raw,
                profile=resolved_profile,
                repeated_noise=repeated_noise,
                repeated_fingerprints=repeated_header_fingerprints,
                trace=trace,
            )
            if normalized:
                pages.append(PdfPageText(page_number=page_number, text=normalized))
    finally:
        document.close()

    if resolved_profile.runtime.pdf.trim_rules_body:
        return trim_us_rules_body_pages(pages)
    return pages


def extract_pdf_text(
    path: str | Path,
    *,
    profile: str | ResolvedProfile = "generic",
    trace: TraceCollector | None = None,
) -> str:
    pages = extract_pdf_pages(path, profile=profile, trace=trace)
    return "\n\n".join(page.text for page in pages).strip()


def coerce_resolved_profile(profile: str | ResolvedProfile) -> ResolvedProfile:
    if hasattr(profile, "runtime") and hasattr(profile, "code"):
        return profile
    return resolve_profile(str(profile))


def trim_us_rules_body_pages(pages: list[PdfPageText]) -> list[PdfPageText]:
    if not pages:
        return pages
    start_index = 0
    for index, page in enumerate(pages):
        if _US_TOC_MARKER_RE.search(page.text):
            continue
        if _US_RULES_BODY_START_RE.search(page.text) and "Rule 1. Scope and Purpose" in page.text:
            start_index = index
            break
    trimmed = pages[start_index:]
    if not trimmed:
        return pages

    first_page = trimmed[0]
    body_start = _US_RULES_BODY_START_RE.search(first_page.text)
    if body_start is not None:
        trimmed_text = first_page.text[body_start.start() :].strip()
        trimmed[0] = PdfPageText(page_number=first_page.page_number, text=trimmed_text)
    return trimmed


def _merge_wrapped_heading_lines(
    lines: list[str],
    *,
    resolved_profile: ResolvedProfile,
) -> list[str]:
    merged_lines: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if is_structural_heading_line(line, profile=resolved_profile.code):
            combined = line
            next_index = idx + 1
            while next_index < len(lines) and looks_like_heading_continuation(
                combined,
                lines[next_index],
                resolved_profile=resolved_profile,
            ):
                combined = join_wrapped_line(combined, lines[next_index])
                next_index += 1
            merged_lines.append(combined)
            idx = next_index
            continue
        merged_lines.append(line)
        idx += 1
    return merged_lines


def _classify_lines(
    lines: list[str],
    *,
    resolved_profile: ResolvedProfile,
) -> list[PdfLineCandidate]:
    return [classify_pdf_line(line, resolved_profile=resolved_profile) for line in lines]


def _candidate_trace_payload(candidate: PdfLineCandidate) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_type": type(candidate).__name__,
        "rule_id": candidate.rule_id,
        "kind": candidate.kind,
        "text": candidate.text,
        "drop": candidate.should_drop,
    }
    if isinstance(candidate, TocLeaderCandidate):
        payload["target_page"] = candidate.target_page
    if isinstance(candidate, StructuralHeadingCandidate) and candidate.heading is not None:
        payload["heading_kind"] = candidate.heading.kind
        payload["heading_label"] = candidate.heading.label
    return payload


__all__ = [
    "PdfPageText",
    "coerce_resolved_profile",
    "extract_pdf_pages",
    "extract_pdf_text",
    "normalize_page_raw_text",
    "trim_us_rules_body_pages",
]
