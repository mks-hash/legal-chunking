"""Public package surface for legal-chunking."""

from legal_chunking.api import chunk_pdf, chunk_text
from legal_chunking.hashing import compute_semantic_hash
from legal_chunking.manifest import load_manifest
from legal_chunking.models import Chunk, Document, Section
from legal_chunking.normalize import normalize_chunk_text, normalize_extracted_text
from legal_chunking.profiles import resolve_profile

__all__ = [
    "Chunk",
    "Document",
    "Section",
    "compute_semantic_hash",
    "chunk_pdf",
    "chunk_text",
    "load_manifest",
    "normalize_chunk_text",
    "normalize_extracted_text",
    "resolve_profile",
]
