"""High-level library API."""

from __future__ import annotations

from pathlib import Path

from legal_chunking.models import Chunk, Document


def chunk_text(text: str, profile: str = "generic", source_name: str = "<memory>") -> Document:
    """Return a deterministic placeholder document for bootstrap wiring."""
    normalized = text.strip()
    chunk = Chunk(chunk_id="chunk-0001", text=normalized, order=1)
    return Document(
        source_name=source_name,
        profile=profile,
        language=None,
        text=normalized,
        chunks=[chunk],
    )


def chunk_pdf(path: str | Path, profile: str = "generic") -> Document:
    """Read a PDF path placeholder until PDF extraction is implemented."""
    source = Path(path)
    return Document(
        source_name=source.name,
        profile=profile,
        language=None,
        text="",
        chunks=[],
    )
