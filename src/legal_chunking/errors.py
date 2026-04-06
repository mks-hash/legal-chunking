"""Library error types for legal-chunking."""

from __future__ import annotations


class LegalChunkingError(Exception):
    """Base exception for library-specific failures."""


class AssetConfigError(LegalChunkingError, ValueError):
    """Raised when packaged manifest or asset payloads are invalid."""


class InvalidProfileError(LegalChunkingError, ValueError):
    """Raised when one profile code or alias cannot be resolved."""


class PdfDependencyError(LegalChunkingError, RuntimeError):
    """Raised when PDF extraction is requested without the optional dependency."""
