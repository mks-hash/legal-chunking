"""Typed PDF extraction models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PdfPageText:
    page_number: int
    text: str


__all__ = ["PdfPageText"]
