"""Detection primitives for legal-chunking."""

from legal_chunking.detect.headings import HeadingMatch, compile_heading_patterns, detect_heading
from legal_chunking.detect.sections import assemble_sections

__all__ = ["HeadingMatch", "assemble_sections", "compile_heading_patterns", "detect_heading"]
