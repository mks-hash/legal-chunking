"""Reviewed source expectations, independent of generated engine snapshots."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from legal_chunking import chunk_text

QUALITY_DIR = Path(__file__).parent / "fixtures" / "quality"
CASES = sorted(QUALITY_DIR.glob("*.json"))


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.stem)
def test_reviewed_legal_structure_preserves_source(path: Path) -> None:
    expected = json.loads(path.read_text(encoding="utf-8"))
    document = chunk_text(
        expected["text"],
        profile=expected["profile"],
        doc_kind=expected["doc_kind"],
        source_name=path.name,
    )
    assert document.text == expected["text"]
    assert len(document.sections) == len(expected["sections"])
    for index, (actual, unit) in enumerate(
        zip(document.sections, expected["sections"], strict=True)
    ):
        assert (actual.title, actual.kind, actual.text) == (
            unit["title"],
            unit["kind"],
            unit["text"],
        )
        parent = unit["parent"]
        assert actual.parent_section_id == (
            document.sections[parent].section_id if parent is not None else None
        )
        assert actual.path == (
            (document.sections[parent].path if parent is not None else []) + [unit["title"]]
        )
        assert actual.order == index
        assert 0 <= actual.start_offset <= actual.end_offset <= len(document.text)
        assert document.text[actual.start_offset : actual.end_offset] == unit["text"]
        for field, value in unit["metadata"].items():
            assert asdict(actual.metadata)[field] == value
    # All own-text spans partition non-whitespace source in its original order.
    assert " ".join(" ".join(s.text for s in document.sections).split()) == " ".join(
        document.text.split()
    )
    assert len(document.chunks) == len(expected["chunks"])
    for index, (actual, unit) in enumerate(zip(document.chunks, expected["chunks"], strict=True)):
        assert actual.text == unit["text"]
        assert actual.chunk_method == unit["method"]
        assert actual.section_id == document.sections[unit["owner"]].section_id
        assert actual.order == index + 1
        assert actual.prev_chunk_id == (document.chunks[index - 1].chunk_id if index else None)
        assert actual.next_chunk_id == (
            document.chunks[index + 1].chunk_id if index + 1 < len(document.chunks) else None
        )
        for field, value in unit["metadata"].items():
            assert asdict(actual.metadata)[field] == value
    assert " ".join(c.text for c in document.chunks) == " ".join(document.text.split())


def test_guidance_without_preamble_has_empty_root_span() -> None:
    document = chunk_text("1. First conclusion.\n2. Second conclusion.", doc_kind="court_guidance")
    assert document.sections[0].text == ""
    assert document.sections[0].start_offset == document.sections[0].end_offset == 0


def test_identity_changes_with_source_name_but_content_does_not() -> None:
    text = "Article 1. Scope\nThe notice must identify the sender."
    first = chunk_text(text, source_name="first.txt")
    renamed = chunk_text(text, source_name="renamed.txt")
    assert first == chunk_text(text, source_name="first.txt")
    assert [s.section_id for s in first.sections] != [s.section_id for s in renamed.sections]
    assert first.chunks[0].chunk_id != renamed.chunks[0].chunk_id
    assert first.chunks[0].semantic_hash == renamed.chunks[0].semantic_hash


def test_insertion_changes_chunk_order_identity_but_preserves_unmoved_section() -> None:
    unit = "Article 2. Notices\nA copy must be retained."
    before = chunk_text(unit)
    after = chunk_text("Article 1. Scope\nThis instrument governs notices.\n" + unit)
    assert before.sections[1].section_id == after.sections[2].section_id
    assert before.chunks[0].chunk_id != after.chunks[1].chunk_id
    assert before.chunks[0].semantic_hash == after.chunks[1].semantic_hash


def test_reparenting_changes_section_identity_without_changing_content() -> None:
    unit = "Article 1. Notices\nA copy must be retained."
    before = chunk_text("Chapter I. Scope\n" + unit)
    after = chunk_text("Chapter II. Records\n" + unit)
    assert before.sections[2].section_id != after.sections[2].section_id
    assert before.chunks[-1].chunk_id != after.chunks[-1].chunk_id
    assert before.chunks[-1].semantic_hash == after.chunks[-1].semantic_hash


def test_identical_repeated_units_keep_distinct_identities_and_equal_hashes() -> None:
    unit = "Article 1. Notices\nA copy must be retained."
    document = chunk_text(unit + "\n" + unit)
    assert document.sections[1].path == document.sections[2].path
    assert document.sections[1].section_id != document.sections[2].section_id
    assert document.chunks[0].chunk_id != document.chunks[1].chunk_id
    assert document.chunks[0].semantic_hash == document.chunks[1].semantic_hash


def test_body_whitespace_preserves_hash_and_chunk_identity_but_moves_offsets() -> None:
    first = chunk_text("Article 1. Notices\nA copy must be retained.")
    spaced = chunk_text("Article 1. Notices\n\nA copy must be retained.")
    assert first.text != spaced.text
    assert first.sections[1].end_offset != spaced.sections[1].end_offset
    assert first.chunks == spaced.chunks


def test_empty_input_has_no_invented_structure() -> None:
    document = chunk_text(" \n\t ")
    assert document.text == ""
    assert document.sections == []
    assert document.chunks == []


def test_reordering_unique_siblings_preserves_section_ids_but_changes_chunk_ids() -> None:
    first = "Article 1. Notices\nA copy must be retained."
    second = "Article 2. Records\nThe clerk must record delivery."
    before = chunk_text(first + "\n" + second)
    after = chunk_text(second + "\n" + first)
    assert before.sections[1].section_id == after.sections[2].section_id
    assert before.sections[2].section_id == after.sections[1].section_id
    assert before.chunks[0].semantic_hash == after.chunks[1].semantic_hash
    assert before.chunks[0].chunk_id != after.chunks[1].chunk_id


def test_body_edit_preserves_section_identity_but_changes_content_and_chunk_id() -> None:
    before = chunk_text("Article 1. Duration\nA notice lasts ten days.")
    after = chunk_text("Article 1. Duration\nA notice lasts twenty days.")
    assert before.sections[1].section_id == after.sections[1].section_id
    assert before.chunks[0].semantic_hash != after.chunks[0].semantic_hash
    assert before.chunks[0].chunk_id != after.chunks[0].chunk_id


def test_preamble_and_parent_spans_exclude_descendants_and_separator_whitespace() -> None:
    text = "Opening statement.\n\nChapter I. Scope\n\nArticle 1. Notices\nA copy is retained."
    document = chunk_text(text)
    assert [s.text for s in document.sections] == [
        "Opening statement.",
        "Chapter I. Scope",
        "Article 1. Notices\nA copy is retained.",
    ]
    for section in document.sections:
        assert document.text[section.start_offset : section.end_offset] == section.text
    assert document.sections[0].end_offset < document.sections[1].start_offset
    assert document.sections[1].end_offset < document.sections[2].start_offset


def test_character_fallback_covers_oversized_unit_without_crossing_next_article() -> None:
    body = " ".join(f"item{index:04d}" for index in range(600))
    text = "Article 1. Inventory\n" + body + "\nArticle 2. Final\nClosing provision."
    document = chunk_text(text)
    chunks = [c for c in document.chunks if c.metadata.article_number == "1"]
    assert len(chunks) > 1
    assert {c.chunk_method for c in chunks} == {"char_fallback"}
    source = " ".join(document.sections[1].text.split())
    covered = set()
    previous = -1
    for chunk in chunks:
        start = source.find(chunk.text, previous + 1)
        assert start >= 0, "Fallback invented or reordered source content"
        covered.update(range(start, start + len(chunk.text)))
        previous = start
        assert chunk.section_id == document.sections[1].section_id
        assert "Article 2" not in chunk.text
    assert all(index in covered for index, char in enumerate(source) if not char.isspace())
    assert document.chunks[-1].text == "Article 2. Final Closing provision."
