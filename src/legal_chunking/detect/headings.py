"""Compatibility facade for staged heading detection modules."""

from __future__ import annotations

from .heading_patterns import compile_heading_patterns
from .heading_runtime import detect_heading
from .heading_types import HeadingMatch

__all__ = ["HeadingMatch", "compile_heading_patterns", "detect_heading"]
