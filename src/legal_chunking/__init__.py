"""Public package surface for legal-chunking."""

from legal_chunking.api import chunk_pdf, chunk_text
from legal_chunking.detect.sections import assemble_sections
from legal_chunking.errors import (
    AssetConfigError,
    InvalidProfileError,
    LegalChunkingError,
    PdfDependencyError,
)
from legal_chunking.models import Chunk, Document, Section
from legal_chunking.reference_parser import ParsedReference, extract_references

__all__ = [
    "AssetConfigError",
    "Chunk",
    "Document",
    "InvalidProfileError",
    "LegalChunkingError",
    "ParsedReference",
    "PdfDependencyError",
    "Section",
    "assemble_sections",
    "chunk_pdf",
    "chunk_text",
    "extract_references",
]
