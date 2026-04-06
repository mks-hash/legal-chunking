"""Runtime policy contracts parsed from asset-backed profile configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        return RuntimePolicy()

    raw_pdf = payload.get("pdf", {})
    raw_chunk = payload.get("chunk", {})
    raw_heading = payload.get("heading", {})

    if not isinstance(raw_pdf, dict):
        raw_pdf = {}
    if not isinstance(raw_chunk, dict):
        raw_chunk = {}
    if not isinstance(raw_heading, dict):
        raw_heading = {}

    return RuntimePolicy(
        pdf=PdfRuntimePolicy(
            drop_line_equals=_normalize_str_tuple(raw_pdf.get("drop_line_equals", [])),
            drop_line_regexes=_normalize_str_tuple(raw_pdf.get("drop_line_regexes", [])),
            trim_rules_body=bool(raw_pdf.get("trim_rules_body", False)),
            trim_running_rule_headers=bool(raw_pdf.get("trim_running_rule_headers", False)),
            merge_wrapped_headings=bool(raw_pdf.get("merge_wrapped_headings", False)),
        ),
        chunk=ChunkRuntimePolicy(
            document_root_splitter=str(raw_chunk.get("document_root_splitter") or "").strip(),
            article_splitter=str(raw_chunk.get("article_splitter") or "").strip(),
            oversized_section_splitter=str(
                raw_chunk.get("oversized_section_splitter") or ""
            ).strip(),
        ),
        heading=HeadingRuntimePolicy(
            allow_long_rule_titles=bool(raw_heading.get("allow_long_rule_titles", False)),
            block_signature_names=bool(raw_heading.get("block_signature_names", False)),
        ),
    )


def _normalize_str_tuple(items: object) -> tuple[str, ...]:
    if not isinstance(items, list):
        return ()
    return tuple(str(item).strip() for item in items if str(item).strip())


__all__ = [
    "ChunkRuntimePolicy",
    "HeadingRuntimePolicy",
    "PdfRuntimePolicy",
    "RuntimePolicy",
    "parse_runtime_policy",
]
