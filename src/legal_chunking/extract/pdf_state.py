"""Macro-state handling for staged PDF extraction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .pdf_candidates import (
    BodyTextCandidate,
    EnumeratedContentCandidate,
    PdfLineCandidate,
    StructuralHeadingCandidate,
    TocLeaderCandidate,
)


class PdfParserState(StrEnum):
    FRONT_MATTER = "front_matter"
    TABLE_OF_CONTENTS = "table_of_contents"
    BODY = "body"


@dataclass(slots=True, frozen=True)
class PdfLineDecision:
    state: PdfParserState
    keep: bool


def decide_pdf_line(
    candidate: PdfLineCandidate,
    *,
    state: PdfParserState,
) -> PdfLineDecision:
    if candidate.should_drop:
        next_state = _advance_state_on_drop(candidate, state=state)
        return PdfLineDecision(state=next_state, keep=False)

    if state == PdfParserState.FRONT_MATTER:
        return _decide_from_front_matter(candidate)
    if state == PdfParserState.TABLE_OF_CONTENTS:
        return _decide_from_toc(candidate)
    return PdfLineDecision(state=PdfParserState.BODY, keep=True)


def _decide_from_front_matter(candidate: PdfLineCandidate) -> PdfLineDecision:
    if isinstance(candidate, StructuralHeadingCandidate):
        return PdfLineDecision(state=PdfParserState.BODY, keep=True)
    if isinstance(candidate, EnumeratedContentCandidate):
        return PdfLineDecision(state=PdfParserState.BODY, keep=True)
    return PdfLineDecision(state=PdfParserState.FRONT_MATTER, keep=True)


def _decide_from_toc(candidate: PdfLineCandidate) -> PdfLineDecision:
    if isinstance(candidate, (StructuralHeadingCandidate, EnumeratedContentCandidate)):
        return PdfLineDecision(state=PdfParserState.BODY, keep=True)
    if isinstance(candidate, BodyTextCandidate):
        return PdfLineDecision(state=PdfParserState.BODY, keep=True)
    return PdfLineDecision(state=PdfParserState.TABLE_OF_CONTENTS, keep=False)


def _advance_state_on_drop(
    candidate: PdfLineCandidate,
    *,
    state: PdfParserState,
) -> PdfParserState:
    if isinstance(candidate, TocLeaderCandidate) and candidate.target_page is not None:
        return PdfParserState.TABLE_OF_CONTENTS
    return state


__all__ = ["PdfLineDecision", "PdfParserState", "decide_pdf_line"]
