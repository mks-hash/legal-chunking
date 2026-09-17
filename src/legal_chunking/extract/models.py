"""Extractor-neutral page text boundary; no legal classification belongs here."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ExtractedPage:
    page_number: int
    text: str
