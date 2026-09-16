"""Line classification for staged section assembly."""

from __future__ import annotations

from .headings import detect_heading
from .section_candidates import (
    BlankSectionLineCandidate,
    HeadingSectionLineCandidate,
    SectionLineCandidate,
    TextSectionLineCandidate,
)


def classify_section_line(
    line: str,
    *,
    offset: int,
    profile: str,
    chunk_policy: str,
    in_article: bool = False,
) -> SectionLineCandidate:
    stripped = (line or "").strip()
    if not stripped:
        return BlankSectionLineCandidate(
            text="",
            offset=offset,
            rule_id="section.line.blank",
        )
    heading = detect_heading(stripped, profile=profile, chunk_policy=chunk_policy)
    if (
        heading is not None
        and in_article
        and chunk_policy == "statute"
        and (heading.detector_kind == "numeric_heading" and heading.kind in {"article", "section"})
    ):
        heading = None
    if heading is not None:
        return HeadingSectionLineCandidate(
            text=stripped,
            offset=offset,
            heading=heading,
            rule_id="section.line.heading",
        )
    return TextSectionLineCandidate(
        text=stripped,
        offset=offset,
        rule_id="section.line.text",
    )


__all__ = ["classify_section_line"]
