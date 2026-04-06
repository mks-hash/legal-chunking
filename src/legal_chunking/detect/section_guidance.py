"""Guidance-specific section assembly."""

from __future__ import annotations

from legal_chunking.detect.guidance import split_guidance_blocks
from legal_chunking.detect.guidance_metadata import extract_guidance_point_metadata
from legal_chunking.detect.guidance_normalization import normalize_guidance_text
from legal_chunking.models import LegalUnitType, Section
from legal_chunking.tracing import TraceCollector, TraceStage

from .section_common import find_block_offset, make_document_root, make_section_id


def assemble_guidance_sections(
    text: str,
    *,
    profile: str,
    doc_kind: str | None,
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
    root = make_document_root(source_name=source_name, order=order, text_length=len(normalized))
    sections.append(root)
    order += 1

    for block in blocks:
        start_offset = find_block_offset(normalized, block.text, search_offset)
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
            root.text = f"{root.text}\n\n{block.text}".strip() if root.text else block.text
            root.end_offset = end_offset
            continue

        label = f"Point {block.point_number}" if block.point_number else "Point"
        path = ["Document", label]
        path_key = tuple(path)
        occurrence = path_occurrences.get(path_key, 0) + 1
        path_occurrences[path_key] = occurrence
        metadata = extract_guidance_point_metadata(
            block.text,
            point_number=block.point_number,
            profile=profile,
            doc_kind=doc_kind,
            extractor_scope="review_point",
        )
        if trace is not None:
            trace.emit(
                TraceStage.ASSEMBLE,
                "guidance_point_detected",
                point_number=metadata.point_number,
                has_case_reference=metadata.source_case_reference is not None,
            )
        sections.append(
            Section(
                section_id=make_section_id(source_name, path, occurrence),
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


__all__ = ["assemble_guidance_sections"]
