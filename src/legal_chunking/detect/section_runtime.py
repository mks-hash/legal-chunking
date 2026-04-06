"""Section assembly runtime orchestration."""

from __future__ import annotations

from legal_chunking.models import Section
from legal_chunking.tracing import TraceCollector, TraceStage

from .headings import HeadingMatch
from .section_candidates import SectionLineKind
from .section_classify import classify_section_line
from .section_common import finalize_section, level_index, make_document_root, make_section_id
from .section_guidance import assemble_guidance_sections


def assemble_sections(
    text: str,
    *,
    profile: str = "generic",
    chunk_policy: str = "default",
    doc_kind: str | None = None,
    source_name: str = "<memory>",
    trace: TraceCollector | None = None,
) -> list[Section]:
    """Build a deterministic section tree from normalized text."""
    normalized = (text or "").strip()
    if not normalized:
        return []

    if chunk_policy == "guidance":
        guidance_sections = assemble_guidance_sections(
            normalized,
            profile=profile,
            doc_kind=doc_kind,
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
        target_level = level_index(match.kind)
        while stack and level_index(stack[-1].kind) >= target_level:
            stack.pop()

        path = [section.title for section in stack] + [match.label]
        path_key = tuple(path)
        occurrence = path_occurrences.get(path_key, 0) + 1
        path_occurrences[path_key] = occurrence
        parent_section_id = stack[-1].section_id if stack else None
        section = Section(
            section_id=make_section_id(source_name, path, occurrence),
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

    root = make_document_root(source_name=source_name, order=order, text_length=len(normalized))
    order += 1
    sections.append(root)
    stack.append(root)
    text_parts_by_id[root.section_id] = []

    for raw_line in raw_lines:
        line = raw_line.rstrip("\n")
        line_offset = search_offset
        search_offset += len(raw_line)
        candidate = classify_section_line(
            line,
            offset=line_offset,
            profile=profile,
            chunk_policy=chunk_policy,
        )
        if trace is not None:
            trace.emit(
                TraceStage.DETECT,
                "section_line_classified",
                rule_id=candidate.rule_id,
                kind=candidate.kind,
                offset=candidate.offset,
                text=candidate.text,
            )
        if candidate.kind == SectionLineKind.BLANK:
            current = stack[-1]
            text_parts_by_id[current.section_id].append("")
            continue

        if candidate.kind == SectionLineKind.HEADING and candidate.heading is not None:
            if trace is not None:
                trace.emit(
                    TraceStage.DETECT,
                    "heading_detected",
                    kind=candidate.heading.kind,
                    label=candidate.heading.label,
                    offset=candidate.offset,
                )
            start_new_section(candidate.heading, candidate.offset)

        current = stack[-1]
        text_parts_by_id[current.section_id].append(candidate.text)
        current.end_offset = line_offset + len(line)

    for section in sections:
        finalize_section(
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


__all__ = ["assemble_sections"]
