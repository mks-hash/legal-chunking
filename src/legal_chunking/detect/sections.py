"""Section tree assembly over normalized text and heading detection."""

from __future__ import annotations

import hashlib

from legal_chunking.detect.headings import HeadingMatch, detect_heading
from legal_chunking.models import Section

LEVEL_ORDER = ["document_root", "part", "chapter", "section", "article", "clause", "paragraph"]


def _level_index(kind: str) -> int:
    if kind == "other":
        return 1
    return LEVEL_ORDER.index(kind) if kind in LEVEL_ORDER else 1


def _make_section_id(source_name: str, path: list[str], occurrence: int) -> str:
    digest = hashlib.sha256(f"{source_name}::{'||'.join(path)}::{occurrence}".encode()).hexdigest()
    return f"sec-{digest[:12]}"


def _finalize_section(section: Section, text_parts: list[str], *, end_offset: int) -> None:
    section.text = "\n".join(part for part in text_parts if part).strip()
    section.end_offset = max(section.start_offset, end_offset)


def assemble_sections(
    text: str,
    *,
    profile: str = "generic",
    chunk_policy: str = "default",
    source_name: str = "<memory>",
) -> list[Section]:
    """Build a deterministic section tree from normalized text."""
    normalized = (text or "").strip()
    if not normalized:
        return []

    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    if not lines:
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

    for line in lines:
        line_offset = normalized.find(line, search_offset)
        if line_offset < 0:
            line_offset = search_offset
        search_offset = line_offset + len(line)

        heading = detect_heading(line, profile=profile, chunk_policy=chunk_policy)
        if heading is not None:
            start_new_section(heading, line_offset)

        current = stack[-1]
        text_parts_by_id[current.section_id].append(line)
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
