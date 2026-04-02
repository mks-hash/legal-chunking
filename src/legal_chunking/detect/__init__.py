"""Detection primitives for legal-chunking."""

from legal_chunking.detect.headings import HeadingMatch, compile_heading_patterns, detect_heading

__all__ = ["HeadingMatch", "compile_heading_patterns", "detect_heading"]
