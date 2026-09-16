"""Runtime policy contracts parsed from asset-backed profile configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legal_chunking.errors import AssetConfigError


@dataclass(slots=True, frozen=True)
class PdfRuntimePolicy:
    drop_line_equals: tuple[str, ...] = ()
    drop_line_regexes: tuple[str, ...] = ()
    trim_rules_body: bool = False
    trim_running_rule_headers: bool = False
    merge_wrapped_headings: bool = False


@dataclass(slots=True, frozen=True)
class ChunkRuntimePolicy:
    document_root_splitter: str = ""
    article_splitter: str = ""
    article_subdivision_regex: str = ""
    preferred_primary_units: tuple[str, ...] = ()
    oversized_section_splitter: str = ""


@dataclass(slots=True, frozen=True)
class HeadingRuntimePolicy:
    allow_long_rule_titles: bool = False
    block_signature_names: bool = False


@dataclass(slots=True, frozen=True)
class RuntimePolicy:
    pdf: PdfRuntimePolicy = PdfRuntimePolicy()
    chunk: ChunkRuntimePolicy = ChunkRuntimePolicy()
    heading: HeadingRuntimePolicy = HeadingRuntimePolicy()


def parse_runtime_policy(chunking_policy: dict[str, Any]) -> RuntimePolicy:
    """Parse optional runtime policy from one chunking-policy asset payload."""
    payload = chunking_policy.get("runtime", {})
    if not isinstance(payload, dict):
        raise AssetConfigError("Runtime policy must be an object")

    raw_pdf = payload.get("pdf", {})
    raw_chunk = payload.get("chunk", {})
    raw_heading = payload.get("heading", {})

    if not isinstance(raw_pdf, dict):
        raise AssetConfigError("Runtime pdf policy must be an object")
    if not isinstance(raw_chunk, dict):
        raise AssetConfigError("Runtime chunk policy must be an object")
    if not isinstance(raw_heading, dict):
        raise AssetConfigError("Runtime heading policy must be an object")

    return RuntimePolicy(
        pdf=PdfRuntimePolicy(
            drop_line_equals=_normalize_str_tuple(raw_pdf.get("drop_line_equals", [])),
            drop_line_regexes=_normalize_str_tuple(raw_pdf.get("drop_line_regexes", [])),
            trim_rules_body=_boolean(raw_pdf, "trim_rules_body"),
            trim_running_rule_headers=_boolean(raw_pdf, "trim_running_rule_headers"),
            merge_wrapped_headings=_boolean(raw_pdf, "merge_wrapped_headings"),
        ),
        chunk=ChunkRuntimePolicy(
            document_root_splitter=_strategy(raw_chunk, "document_root_splitter"),
            article_splitter=_strategy(raw_chunk, "article_splitter"),
            article_subdivision_regex=_strategy(raw_chunk, "article_subdivision_regex"),
            preferred_primary_units=_normalize_str_tuple(
                raw_chunk.get("preferred_primary_units", [])
            ),
            oversized_section_splitter=_strategy(raw_chunk, "oversized_section_splitter"),
        ),
        heading=HeadingRuntimePolicy(
            allow_long_rule_titles=_boolean(raw_heading, "allow_long_rule_titles"),
            block_signature_names=_boolean(raw_heading, "block_signature_names"),
        ),
    )


def _normalize_str_tuple(items: object) -> tuple[str, ...]:
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise AssetConfigError("Runtime pattern lists must contain strings")
    return tuple(item.strip() for item in items if item.strip())


def _boolean(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key, False)
    if not isinstance(value, bool):
        raise AssetConfigError(f"Runtime {key} must be a boolean")
    return value


def _strategy(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise AssetConfigError(f"Runtime {key} must be a string")
    return value.strip()


__all__ = [
    "ChunkRuntimePolicy",
    "HeadingRuntimePolicy",
    "PdfRuntimePolicy",
    "RuntimePolicy",
    "parse_runtime_policy",
]
