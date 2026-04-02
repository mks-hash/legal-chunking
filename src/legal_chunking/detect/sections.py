"""Section tree assembly over normalized text and heading detection."""

from __future__ import annotations

import hashlib

from legal_chunking.detect.guidance import (
    extract_guidance_point_metadata,
    normalize_guidance_text,
    split_guidance_blocks,
)
from legal_chunking.detect.headings import HeadingMatch, detect_heading
from legal_chunking.models import LegalUnitType, Section
from legal_chunking.tracing import TraceCollector, TraceStage

LEVEL_ORDER = ["document_root", "part", "chapter", "section", "article", "clause", "paragraph"]


def _level_index(kind: str) -> int:
    if kind == "other":
        return 1
    return LEVEL_ORDER.index(kind) if kind in LEVEL_ORDER else 1


def _make_section_id(source_name: str, path: list[str], occurrence: int) -> str:
    digest = hashlib.sha256(f"{source_name}::{'||'.join(path)}::{occurrence}".encode()).hexdigest()
    return f"sec-{digest[:12]}"


def _finalize_section(section: Section, text_parts: list[str], *, end_offset: int) -> None:
    normalized_parts: list[str] = []
    for part in text_parts:
        if part:
            normalized_parts.append(part)
            continue
        if normalized_parts and normalized_parts[-1] != "":
            normalized_parts.append("")
    section.text = "\n".join(normalized_parts).strip()
    section.end_offset = max(section.start_offset, end_offset)


def assemble_sections(
    text: str,
    *,
    profile: str = "generic",
    chunk_policy: str = "default",
    source_name: str = "<memory>",
    trace: TraceCollector | None = None,
) -> list[Section]:
    """Build a deterministic section tree from normalized text."""
    normalized = (text or "").strip()
    if not normalized:
        return []

    if chunk_policy == "guidance":
        guidance_sections = _assemble_guidance_sections(
            normalized,
            source_name=source_name,
            trace=trace,
        )
        if guidance_sections is not None:
            return guidance_sections

    raw_lines = normalized.splitlines(keepends=True)
    if not raw_lines:
        return []

    sections: list[Section] = []
    stack: list[Section] = []
    text_parts_by_id: dict[str, list[str]] = {}
    path_occurrences: dict[tuple[str, ...], int] = {}
    search_offset = 0
    order = 0

    def start_new_section(match: HeadingMatch, start_offset: int) -> Section:
        nonlocal order
        target_level = _level_index(match.kind)
        while stack and _level_index(stack[-1].kind) >= target_level:
            stack.pop()

        path = [section.title for section in stack] + [match.label]
        path_key = tuple(path)
        occurrence = path_occurrences.get(path_key, 0) + 1
        path_occurrences[path_key] = occurrence
        parent_section_id = stack[-1].section_id if stack else None
        section = Section(
            section_id=_make_section_id(source_name, path, occurrence),
            kind=match.kind,
            title=match.label,
            order=order,
            section_type=match.kind,
            parent_section_id=parent_section_id,
            path=path,
            article_number=match.article_number,
            paragraph_number=match.paragraph_number,
            start_offset=start_offset,
            end_offset=start_offset,
            text="",
        )
        order += 1
        stack.append(section)
        sections.append(section)
        text_parts_by_id[section.section_id] = []
        return section

    root = Section(
        section_id=_make_section_id(source_name, ["Document"], 1),
        kind="document_root",
        title="Document",
        order=order,
        section_type="document_root",
        parent_section_id=None,
        path=["Document"],
        start_offset=0,
        end_offset=len(normalized),
        text="",
    )
    order += 1
    sections.append(root)
    stack.append(root)
    text_parts_by_id[root.section_id] = []

    for raw_line in raw_lines:
        line = raw_line.rstrip("\n")
        line_offset = search_offset
        search_offset += len(raw_line)
        stripped = line.strip()
        if not stripped:
            current = stack[-1]
            text_parts_by_id[current.section_id].append("")
            continue

        heading = detect_heading(stripped, profile=profile, chunk_policy=chunk_policy)
        if heading is not None:
            if trace is not None:
                trace.emit(
                    TraceStage.DETECT,
                    "heading_detected",
                    kind=heading.kind,
                    label=heading.label,
                    offset=line_offset,
                )
            start_new_section(heading, line_offset)

        current = stack[-1]
        text_parts_by_id[current.section_id].append(stripped)
        current.end_offset = line_offset + len(line)

    for section in sections:
        _finalize_section(
            section,
            text_parts_by_id.get(section.section_id, []),
            end_offset=section.end_offset,
        )

    non_empty_sections = [section for section in sections if section.text]
    if len(non_empty_sections) == 1 and non_empty_sections[0].kind == "document_root":
        return non_empty_sections

    result: list[Section] = [root]
    result.extend(section for section in sections[1:] if section.text)
    return result


def _assemble_guidance_sections(
    text: str,
    *,
    source_name: str,
    trace: TraceCollector | None = None,
) -> list[Section] | None:
    normalized = normalize_guidance_text(text)
    if not normalized:
        return []

    blocks = split_guidance_blocks(
        normalized,
        allow_noninitial_sequence=True,
        min_points=1,
    )
    if not any(block.method == "guidance_point" for block in blocks):
        return None

    sections: list[Section] = []
    path_occurrences: dict[tuple[str, ...], int] = {}
    search_offset = 0
    order = 0

    root = Section(
        section_id=_make_section_id(source_name, ["Document"], 1),
        kind="document_root",
        title="Document",
        order=order,
        section_type="document_root",
        parent_section_id=None,
        path=["Document"],
        start_offset=0,
        end_offset=len(normalized),
        text="",
    )
    sections.append(root)
    order += 1

    for block in blocks:
        start_offset = _find_block_offset(normalized, block.text, search_offset)
        end_offset = start_offset + len(block.text)
        search_offset = end_offset

        if block.method == "guidance_preamble":
            root.text = block.text
            root.end_offset = end_offset
            if trace is not None:
                trace.emit(
                    TraceStage.ASSEMBLE,
                    "guidance_preamble_detected",
                    char_length=len(block.text),
                )
            continue

        if block.method != "guidance_point":
            if root.text:
                root.text = f"{root.text}\n\n{block.text}".strip()
            else:
                root.text = block.text
            root.end_offset = end_offset
            continue

        label = f"Point {block.point_number}" if block.point_number else "Point"
        path = ["Document", label]
        path_key = tuple(path)
        occurrence = path_occurrences.get(path_key, 0) + 1
        path_occurrences[path_key] = occurrence
        metadata = extract_guidance_point_metadata(block.text, point_number=block.point_number)
        if trace is not None:
            trace.emit(
                TraceStage.ASSEMBLE,
                "guidance_point_detected",
                point_number=metadata.point_number,
                has_case_reference=metadata.source_case_reference is not None,
            )
        sections.append(
            Section(
                section_id=_make_section_id(source_name, path, occurrence),
                kind="clause",
                title=label,
                order=order,
                section_type="review_point",
                parent_section_id=root.section_id,
                path=path,
                point_number=metadata.point_number,
                legal_unit_type=LegalUnitType.GUIDANCE_POINT,
                legal_unit_number=metadata.point_number,
                source_case_reference=metadata.source_case_reference,
                source_case_number=metadata.source_case_number,
                source_case_date=metadata.source_case_date,
                source_case_court=metadata.source_case_court,
                start_offset=start_offset,
                end_offset=end_offset,
                text=block.text,
            )
        )
        order += 1

    return sections


def _find_block_offset(text: str, block: str, start: int) -> int:
    index = text.find(block, start)
    if index >= 0:
        return index
    fallback = text.find(block)
    return fallback if fallback >= 0 else start
