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
        expected.get("input_text", expected["text"]),
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


def test_definition_metadata_does_not_delete_table_header_words_from_prose() -> None:
    from legal_chunking.detect.definitions import parse_definition_entries

    entries = parse_definition_entries(
        '"Notice" means a written communication. The phrase term definition is operative text.'
    )
    assert entries[0].definition == (
        "means a written communication. The phrase term definition is operative text."
    )


def test_definition_schedule_without_recognized_entries_preserves_all_text() -> None:
    text = "Schedule 1 - Definitions\nA notice is a written communication."
    document = chunk_text(text, profile="ae")
    assert [c.text for c in document.chunks] == [" ".join(text.split())]
    assert document.chunks[0].chunk_method == "statute_unit"


def test_long_recitals_preserve_numbered_units_before_operative_articles() -> None:
    first = "(1) " + " ".join(["Notices should identify their sender."] * 22)
    second = "(2) " + " ".join(["Records should remain accessible."] * 24)
    article = "Article 1. Notices\nA notice shall identify its sender."
    document = chunk_text("Whereas:\n" + first + "\n" + second + "\n\n" + article, profile="eu")
    assert [c.text for c in document.chunks] == [
        "Whereas: " + first,
        second,
        " ".join(article.split()),
    ]
    assert [c.chunk_method for c in document.chunks] == ["statute_unit"] * 3
    assert (
        document.chunks[0].section_id
        == document.chunks[1].section_id
        == document.sections[0].section_id
    )
    assert document.chunks[2].metadata.article_number == "1"
    assert " ".join(c.text for c in document.chunks) == " ".join(document.text.split())


def test_noisy_native_pdf_preserves_repeated_operative_text(tmp_path: Path) -> None:
    import pymupdf

    from legal_chunking import chunk_pdf

    path = tmp_path / "registry.pdf"
    units = [
        f"Article {number}. Notices\nA notice must identify its sender." for number in range(1, 4)
    ]
    with pymupdf.open() as pdf:
        for number, unit in enumerate(units, 1):
            page = pdf.new_page()
            page.insert_text((72, 72), f"Example Registry Bulletin\n{unit}\n{number}")
        pdf.save(path)
    original = path.read_bytes()
    document = chunk_pdf(path, trace=True)
    assert document.text == "\n\n".join(units)
    assert [s.text for s in document.sections] == ["", *units]
    assert [c.text for c in document.chunks] == [" ".join(unit.split()) for unit in units]
    for section in document.sections:
        assert document.text[section.start_offset : section.end_offset] == section.text
    assert path.read_bytes() == original
    assert document.trace is not None
    assert "Example Registry Bulletin" not in document.text
    # Repetition alone must not authorize deleting the operative sentence.
    assert document.text.count("A notice must identify its sender.") == 3


def test_repeated_heading_and_sentence_at_page_start_are_not_margin_noise() -> None:
    from legal_chunking.extract.pdf import _normalize_page_raw_text
    from legal_chunking.extract.pdf_rules import (
        find_repeated_leading_header_fingerprints,
        find_repeated_page_noise,
    )

    lines = ["Article 1. Notices", "A notice must identify its sender."]
    noise = find_repeated_page_noise([lines] * 3)
    fingerprints = find_repeated_leading_header_fingerprints([lines] * 3)
    assert _normalize_page_raw_text(
        "\n".join(lines),
        repeated_noise=noise,
        repeated_fingerprints=fingerprints,
        profile="generic",
    ) == "\n".join(lines)


def test_repeated_header_text_inside_article_is_preserved() -> None:
    from legal_chunking.extract.pdf import _normalize_page_raw_text

    text = (
        "Example Registry Bulletin\nArticle 1. Notices\n"
        "Example Registry Bulletin\nA notice must identify its sender."
    )
    normalized = _normalize_page_raw_text(
        text, profile="generic", repeated_noise={"Example Registry Bulletin"}
    )
    assert (
        normalized
        == "Article 1. Notices\nExample Registry Bulletin A notice must identify its sender."
    )


def test_repeated_footer_date_is_not_a_legal_heading() -> None:
    from legal_chunking.extract.pdf import _normalize_page_raw_text

    text = (
        "Article 1. Notices\nA notice must identify its sender.\n4.5.2016\nExample Registry Journal"
    )
    assert (
        _normalize_page_raw_text(
            text, profile="generic", repeated_noise={"4.5.2016", "Example Registry Journal"}
        )
        == "Article 1. Notices\nA notice must identify its sender."
    )


def test_repeated_court_label_inside_body_survives_cleanup() -> None:
    from legal_chunking.extract.pdf import _normalize_page_raw_text

    label = "Определение Судебной коллегии по гражданским делам Верховного Суда РФ"
    text = "1. Вывод суда.\n" + label + "\nот 28 ноября 2023 г. № 44-КГ23-24-К7."
    result = _normalize_page_raw_text(text, profile="ru", repeated_noise={label})
    assert label in result
    assert "44-КГ23-24-К7" in result


def test_restored_primary_court_label_prevents_selecting_analogous_case_instead() -> None:
    label = "Определение Судебной коллегии по гражданским делам Верховного Суда РФ"
    primary = label + " от 23 января 2024 г. № 2-КГ23-8-К3"
    text = (
        "Обзор судебной практики\n1. Заявителю направляется копия решения.\n"
        + primary
        + "\nАналогичная позиция изложена также в определениях "
        "Судебной коллегии по гражданским делам Верховного Суда РФ "
        "от 2 апреля 2024 г. № 5-КГ24-11-К2."
    )
    document = chunk_text(text, profile="ru", doc_kind="court_guidance")
    metadata = document.sections[1].metadata
    assert metadata.source_case_reference == primary
    assert metadata.source_case_number == "2-КГ23-8-К3"
    assert metadata.source_case_date == "23 января 2024 г."
    assert metadata.source_case_court == "Верховный Суд РФ"


def test_repeated_numeric_heading_alone_at_page_end_is_not_a_footer_block() -> None:
    from legal_chunking.extract.pdf import _normalize_page_raw_text

    text = "Article 1. Notices\n4.5 Scope"
    assert _normalize_page_raw_text(text, profile="generic", repeated_noise={"4.5 Scope"}) == text
