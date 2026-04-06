"""Typed candidates for section assembly line classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .heading_types import HeadingMatch


class SectionLineKind(StrEnum):
    BLANK = "blank"
    HEADING = "heading"
    TEXT = "text"


@dataclass(slots=True, frozen=True)
class SectionLineCandidate:
    text: str
    offset: int
    rule_id: str

    @property
    def kind(self) -> SectionLineKind:
        raise NotImplementedError


@dataclass(slots=True, frozen=True)
class BlankSectionLineCandidate(SectionLineCandidate):
    @property
    def kind(self) -> SectionLineKind:
        return SectionLineKind.BLANK


@dataclass(slots=True, frozen=True)
class HeadingSectionLineCandidate(SectionLineCandidate):
    heading: HeadingMatch

    @property
    def kind(self) -> SectionLineKind:
        return SectionLineKind.HEADING


@dataclass(slots=True, frozen=True)
class TextSectionLineCandidate(SectionLineCandidate):
    @property
    def kind(self) -> SectionLineKind:
        return SectionLineKind.TEXT


__all__ = [
    "BlankSectionLineCandidate",
    "HeadingSectionLineCandidate",
    "SectionLineCandidate",
    "SectionLineKind",
    "TextSectionLineCandidate",
]
