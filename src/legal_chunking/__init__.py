"""Public package surface for legal-chunking."""

from legal_chunking.api import chunk_pdf, chunk_text
from legal_chunking.chunk import build_chunks
from legal_chunking.detect.headings import HeadingMatch, compile_heading_patterns, detect_heading
from legal_chunking.detect.sections import assemble_sections
from legal_chunking.hashing import compute_semantic_hash
from legal_chunking.manifest import load_manifest
from legal_chunking.models import Chunk, Document, Section
from legal_chunking.normalize import normalize_chunk_text, normalize_extracted_text
from legal_chunking.numbering_markers import (
    build_numbering_marker_pattern,
    get_numbering_aliases,
    get_numbering_family_aliases,
)
from legal_chunking.profiles import (
    resolve_doc_family,
    resolve_profile,
    select_chunk_fallback,
    select_chunk_policy,
)
from legal_chunking.reference_context import ReferenceContext, ReferenceContextResolver
from legal_chunking.reference_parser import ParsedReference, extract_references, normalize_reference
from legal_chunking.references import (
    normalize_article_number,
    normalize_legal_query_text,
    normalize_legal_text,
    normalize_normalized_ref,
    normalize_normalized_refs,
    normalize_numeric_scripts,
)

__all__ = [
    "Chunk",
    "Document",
    "HeadingMatch",
    "ParsedReference",
    "ReferenceContext",
    "ReferenceContextResolver",
    "Section",
    "assemble_sections",
    "build_chunks",
    "build_numbering_marker_pattern",
    "compile_heading_patterns",
    "compute_semantic_hash",
    "detect_heading",
    "extract_references",
    "get_numbering_aliases",
    "get_numbering_family_aliases",
    "chunk_pdf",
    "chunk_text",
    "load_manifest",
    "normalize_article_number",
    "normalize_chunk_text",
    "normalize_extracted_text",
    "normalize_legal_query_text",
    "normalize_legal_text",
    "normalize_normalized_ref",
    "normalize_normalized_refs",
    "normalize_numeric_scripts",
    "normalize_reference",
    "resolve_profile",
    "resolve_doc_family",
    "select_chunk_fallback",
    "select_chunk_policy",
]
