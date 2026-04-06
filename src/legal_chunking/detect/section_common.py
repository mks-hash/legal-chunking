"""Shared section assembly helpers."""

from __future__ import annotations

import hashlib

from legal_chunking.models import Section

LEVEL_ORDER = ["document_root", "part", "chapter", "section", "article", "clause", "paragraph"]


def level_index(kind: str) -> int:
    if kind == "other":
        return 1
    return LEVEL_ORDER.index(kind) if kind in LEVEL_ORDER else 1


def make_section_id(source_name: str, path: list[str], occurrence: int) -> str:
    digest = hashlib.sha256(f"{source_name}::{'||'.join(path)}::{occurrence}".encode()).hexdigest()
    return f"sec-{digest[:12]}"


def finalize_section(section: Section, text_parts: list[str], *, end_offset: int) -> None:
    normalized_parts: list[str] = []
    for part in text_parts:
        if part:
            normalized_parts.append(part)
            continue
        if normalized_parts and normalized_parts[-1] != "":
            normalized_parts.append("")
    section.text = "\n".join(normalized_parts).strip()
    section.end_offset = max(section.start_offset, end_offset)


def make_document_root(
    *,
    source_name: str,
    order: int,
    text_length: int,
) -> Section:
    return Section(
        section_id=make_section_id(source_name, ["Document"], 1),
        kind="document_root",
        title="Document",
        order=order,
        section_type="document_root",
        parent_section_id=None,
        path=["Document"],
        start_offset=0,
        end_offset=text_length,
        text="",
    )


def find_block_offset(text: str, block: str, start: int) -> int:
    index = text.find(block, start)
    if index >= 0:
        return index
    fallback = text.find(block)
    return fallback if fallback >= 0 else start


__all__ = [
    "LEVEL_ORDER",
    "finalize_section",
    "find_block_offset",
    "level_index",
    "make_document_root",
    "make_section_id",
]
