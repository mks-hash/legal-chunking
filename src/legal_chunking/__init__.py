"""Public package surface for legal-chunking."""

from legal_chunking.api import chunk_pdf, chunk_text
from legal_chunking.models import Chunk, Document, Section

__all__ = [
    "Chunk",
    "Document",
    "Section",
    "chunk_pdf",
    "chunk_text",
]
