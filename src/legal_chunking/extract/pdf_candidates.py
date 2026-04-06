"""Typed candidates for staged PDF line classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from legal_chunking.detect.heading_types import HeadingMatch


class PdfLineKind(StrEnum):
    BLANK = "blank"
    PAGE_NUMBER = "page_number"
    RUNNING_HEADER = "running_header"
    PROFILE_NOISE = "profile_noise"
    TOC_LEADER = "toc_leader"
    STRUCTURAL_HEADING = "structural_heading"
    ENUMERATED_CONTENT = "enumerated_content"
    BODY_TEXT = "body_text"


@dataclass(slots=True, frozen=True)
class PdfLineCandidate:
    text: str
    rule_id: str
    should_drop: bool = False

    @property
    def kind(self) -> PdfLineKind:
        raise NotImplementedError


@dataclass(slots=True, frozen=True)
class BlankLineCandidate(PdfLineCandidate):
    @property
    def kind(self) -> PdfLineKind:
        return PdfLineKind.BLANK


@dataclass(slots=True, frozen=True)
class PageNumberCandidate(PdfLineCandidate):
    @property
    def kind(self) -> PdfLineKind:
        return PdfLineKind.PAGE_NUMBER


@dataclass(slots=True, frozen=True)
class RunningHeaderCandidate(PdfLineCandidate):
    @property
    def kind(self) -> PdfLineKind:
        return PdfLineKind.RUNNING_HEADER


@dataclass(slots=True, frozen=True)
class ProfileNoiseCandidate(PdfLineCandidate):
    @property
    def kind(self) -> PdfLineKind:
        return PdfLineKind.PROFILE_NOISE


@dataclass(slots=True, frozen=True)
class TocLeaderCandidate(PdfLineCandidate):
    target_page: int | None = None

    @property
    def kind(self) -> PdfLineKind:
        return PdfLineKind.TOC_LEADER


@dataclass(slots=True, frozen=True)
class StructuralHeadingCandidate(PdfLineCandidate):
    heading: HeadingMatch | None = None

    @property
    def kind(self) -> PdfLineKind:
        return PdfLineKind.STRUCTURAL_HEADING


@dataclass(slots=True, frozen=True)
class EnumeratedContentCandidate(PdfLineCandidate):
    @property
    def kind(self) -> PdfLineKind:
        return PdfLineKind.ENUMERATED_CONTENT


@dataclass(slots=True, frozen=True)
class BodyTextCandidate(PdfLineCandidate):
    @property
    def kind(self) -> PdfLineKind:
        return PdfLineKind.BODY_TEXT


__all__ = [
    "BlankLineCandidate",
    "BodyTextCandidate",
    "EnumeratedContentCandidate",
    "PageNumberCandidate",
    "PdfLineCandidate",
    "PdfLineKind",
    "ProfileNoiseCandidate",
    "RunningHeaderCandidate",
    "StructuralHeadingCandidate",
    "TocLeaderCandidate",
]
