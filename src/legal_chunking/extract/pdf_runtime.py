"""PDF extraction runtime orchestration over staged line rules."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from legal_chunking.normalize import normalize_extracted_text
from legal_chunking.profiles import resolve_profile
from legal_chunking.tracing import TraceCollector, TraceStage

from .backends import extract_pages
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
    is_structural_heading_line,
    join_wrapped_line,
    looks_like_heading_continuation,
    match_profile_noise_rule,
    merge_marker_lines,
    normalize_line_text,
    trim_leading_header_fragments,
    trim_trailing_header_fragments,
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
    page_number: int | None = None,
) -> str:
    resolved_profile = coerce_resolved_profile(profile)
    raw = (raw or "").replace("\r", "\n")
    lines: list[str] = []
    line_numbers: list[int] = []
    for number, raw_line in enumerate(raw.split("\n"), 1):
        line = normalize_line_text(raw_line)
        if not line:
            continue
        noise_rule = match_profile_noise_rule(line, resolved_profile=resolved_profile)
        if noise_rule is not None:
            if trace is not None:
                trace.emit(
                    TraceStage.EXTRACT,
                    "pdf_text_removed",
                    rule_id=f"pdf.line.profile_noise.{resolved_profile.code}",
                    reason="profile_noise",
                    text=line,
                    page_number=page_number,
                    line_number=number,
                    input_stage="normalized_page_lines",
                    policy_field=noise_rule[0],
                    policy_value=noise_rule[1],
                )
            continue
        lines.append(line)
        line_numbers.append(number)

    def record_trim(remaining: list[str], rule_id: str, *, trailing: bool = False) -> None:
        nonlocal lines, line_numbers
        removed_count = len(lines) - len(remaining)
        cut = len(remaining) if trailing else removed_count
        removed_lines = lines[cut:] if trailing else lines[:cut]
        removed_numbers = line_numbers[cut:] if trailing else line_numbers[:cut]
        if trace is not None:
            for text, number in zip(removed_lines, removed_numbers, strict=True):
                trace.emit(
                    TraceStage.EXTRACT,
                    "pdf_text_removed",
                    rule_id=rule_id,
                    reason="trailing_margin" if trailing else "leading_margin",
                    text=text,
                    page_number=page_number,
                    line_number=number,
                    input_stage="normalized_page_lines",
                )
        lines = remaining
        line_numbers = line_numbers[:cut] if trailing else line_numbers[cut:]

    record_trim(
        trim_leading_header_fragments(
            lines,
            repeated_noise=repeated_noise,
            repeated_fingerprints=repeated_fingerprints,
            profile=resolved_profile.code,
        ),
        "pdf.margin.repeated_leading",
    )
    record_trim(
        trim_trailing_header_fragments(
            lines,
            repeated_noise=repeated_noise,
            profile=resolved_profile.code,
        ),
        "pdf.margin.repeated_trailing",
        trailing=True,
    )
    if resolved_profile.runtime.pdf.trim_running_rule_headers:
        record_trim(trim_us_running_rule_header(lines), "pdf.margin.us_running_rule")
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
        if trace is not None:
            trace.emit(
                TraceStage.EXTRACT,
                "pdf_page_removed",
                rule_id="pdf.page.toc_leader_cluster",
                reason="toc_leader_cluster",
                page_number=page_number,
                toc_leader_count=len(toc_candidates),
                text="\n".join(item.text for item in classified_lines),
                input_stage="normalized_page_lines",
            )
        return ""
    if trace is not None:
        for candidate, number in zip(classified_lines, line_numbers, strict=True):
            if candidate.should_drop:
                trace.emit(
                    TraceStage.EXTRACT,
                    "pdf_text_removed",
                    rule_id=candidate.rule_id,
                    reason=candidate.kind,
                    text=candidate.text,
                    page_number=page_number,
                    line_number=number,
                    input_stage="normalized_page_lines",
                )
    lines = merge_marker_lines([item.text for item in classified_lines if not item.should_drop])
    if resolved_profile.runtime.pdf.merge_wrapped_headings:
        lines = _merge_wrapped_heading_lines(lines, resolved_profile=resolved_profile)
    refined_candidates = _classify_lines(lines, resolved_profile=resolved_profile)

    paragraphs: list[str] = []
    buffer: list[str] = []
    state = PdfParserState.FRONT_MATTER
    for number, candidate in enumerate(refined_candidates, 1):
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
            if trace is not None:
                trace.emit(
                    TraceStage.EXTRACT,
                    "pdf_text_removed",
                    rule_id=candidate.rule_id,
                    reason="parser_state_rejected",
                    text=candidate.text,
                    page_number=page_number,
                    line_number=number,
                    input_stage="refined_page_lines",
                    state=decision.state,
                )
            continue
        if buffer and re.search(r"\d-$", buffer[-1]) and re.match(r"\d+-[^\W\d_]", candidate.text):
            append_line(buffer, candidate.text, profile=resolved_profile.code)
            if trace is not None:
                trace.emit(
                    TraceStage.EXTRACT,
                    "pdf_wrapped_identifier_joined",
                    rule_id="pdf.context.wrapped_numeric_identifier",
                )
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
    backend: str = "pymupdf",
    ocr: str = "off",
    ocr_language: str = "eng",
    ocr_dpi: int = 300,
) -> list[PdfPageText]:
    """Extract normalized page text from a PDF with deterministic cleanup."""
    resolved_profile = coerce_resolved_profile(profile)
    raw_pages = extract_pages(
        path, backend=backend, ocr=ocr, ocr_language=ocr_language, ocr_dpi=ocr_dpi, trace=trace
    )
    normalized_line_pages = [
        [line for part in page.text.splitlines() if (line := normalize_line_text(part))]
        for page in raw_pages
        if page.text.strip()
    ]
    repeated_noise = find_repeated_page_noise(normalized_line_pages)
    repeated_fingerprints = find_repeated_leading_header_fingerprints(normalized_line_pages)
    pages: list[PdfPageText] = []
    for page in raw_pages:
        normalized = normalize_page_raw_text(
            page.text,
            profile=resolved_profile,
            repeated_noise=repeated_noise,
            repeated_fingerprints=repeated_fingerprints,
            trace=trace,
            page_number=page.page_number,
        )
        if normalized:
            pages.append(PdfPageText(page_number=page.page_number, text=normalized))

    if resolved_profile.runtime.pdf.trim_rules_body:
        return trim_us_rules_body_pages(pages, trace=trace)
    return pages


def extract_pdf_text(
    path: str | Path,
    *,
    profile: str | ResolvedProfile = "generic",
    trace: TraceCollector | None = None,
    backend: str = "pymupdf",
    ocr: str = "off",
    ocr_language: str = "eng",
    ocr_dpi: int = 300,
) -> str:
    pages = extract_pdf_pages(
        path,
        profile=profile,
        trace=trace,
        backend=backend,
        ocr=ocr,
        ocr_language=ocr_language,
        ocr_dpi=ocr_dpi,
    )
    return "\n\n".join(page.text for page in pages).strip()


def coerce_resolved_profile(profile: str | ResolvedProfile) -> ResolvedProfile:
    if hasattr(profile, "runtime") and hasattr(profile, "code"):
        return profile
    return resolve_profile(str(profile))


def trim_us_rules_body_pages(
    pages: list[PdfPageText], *, trace: TraceCollector | None = None
) -> list[PdfPageText]:
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

    if trace is not None:
        for page in pages[:start_index]:
            trace.emit(
                TraceStage.EXTRACT,
                "pdf_page_removed",
                rule_id="pdf.document.us_rules_front_matter",
                reason="before_rules_body",
                page_number=page.page_number,
                text=page.text,
                input_stage="cleaned_page_text",
            )
    first_page = trimmed[0]
    body_start = _US_RULES_BODY_START_RE.search(first_page.text)
    if body_start is not None:
        if trace is not None and body_start.start() > 0:
            trace.emit(
                TraceStage.EXTRACT,
                "pdf_text_removed",
                rule_id="pdf.document.us_rules_body_prefix",
                reason="before_rules_body",
                page_number=first_page.page_number,
                text=first_page.text[: body_start.start()],
                start_offset=0,
                end_offset=body_start.start(),
                input_stage="cleaned_page_text",
            )
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
