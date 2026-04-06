"""Line classification for staged PDF extraction."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from legal_chunking.detect.headings import detect_heading

from .pdf_candidates import (
    BlankLineCandidate,
    BodyTextCandidate,
    EnumeratedContentCandidate,
    PageNumberCandidate,
    PdfLineCandidate,
    ProfileNoiseCandidate,
    RunningHeaderCandidate,
    StructuralHeadingCandidate,
    TocLeaderCandidate,
)
from .pdf_rules import (
    has_toc_leader,
    is_enumerated_content_line,
    is_page_number_line,
    is_profile_specific_noise_line,
    is_running_header_line,
    is_structural_heading_line,
)

if TYPE_CHECKING:
    from legal_chunking.profiles import ResolvedProfile

_TOC_TARGET_PAGE_RE = re.compile(r"(?P<page>\d{1,4})\s*$")


def classify_pdf_line(line: str, *, resolved_profile: ResolvedProfile) -> PdfLineCandidate:
    normalized = (line or "").strip()
    if not normalized:
        return BlankLineCandidate(
            text="",
            rule_id="pdf.line.blank",
            should_drop=True,
        )
    if is_page_number_line(normalized):
        return PageNumberCandidate(
            text=normalized,
            rule_id="pdf.line.page_number",
            should_drop=True,
        )
    if has_toc_leader(normalized):
        return TocLeaderCandidate(
            text=normalized,
            rule_id="pdf.line.toc_leader",
            should_drop=True,
            target_page=_extract_toc_target_page(normalized),
        )
    if is_running_header_line(normalized):
        return RunningHeaderCandidate(
            text=normalized,
            rule_id="pdf.line.running_header",
            should_drop=True,
        )
    if is_profile_specific_noise_line(normalized, resolved_profile=resolved_profile):
        return ProfileNoiseCandidate(
            text=normalized,
            rule_id=f"pdf.line.profile_noise.{resolved_profile.code}",
            should_drop=True,
        )
    heading = detect_heading(normalized, profile=resolved_profile.code)
    if heading is not None or is_structural_heading_line(normalized, profile=resolved_profile.code):
        return StructuralHeadingCandidate(
            text=normalized,
            rule_id="pdf.line.structural_heading",
            heading=heading,
        )
    if is_enumerated_content_line(normalized):
        return EnumeratedContentCandidate(
            text=normalized,
            rule_id="pdf.line.enumerated_content",
        )
    return BodyTextCandidate(
        text=normalized,
        rule_id="pdf.line.body_text",
    )


__all__ = ["classify_pdf_line"]


def _extract_toc_target_page(text: str) -> int | None:
    match = _TOC_TARGET_PAGE_RE.search(text or "")
    if match is None:
        return None
    return int(match.group("page"))
