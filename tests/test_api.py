from pathlib import Path

import fitz

from legal_chunking import chunk_pdf, chunk_text
from legal_chunking.hashing import compute_semantic_hash
from legal_chunking.normalize import normalize_chunk_text, normalize_extracted_text

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_chunk_text_returns_document() -> None:
    document = chunk_text("  Article 1.   Test clause  ")

    assert document.profile == "generic"
    assert document.text == "Article 1. Test clause"
    assert len(document.chunks) == 1
    assert document.chunks[0].text == "Article 1. Test clause"
    assert document.chunks[0].semantic_hash == compute_semantic_hash("Article 1. Test clause")
    assert document.chunks[0].chunk_id.startswith("chunk-")
    assert document.chunks[0].chunk_method == "statute_unit"
    assert document.chunks[0].prev_chunk_id is None
    assert document.chunks[0].next_chunk_id is None
    assert document.chunk_policy == "statute"


def test_chunk_pdf_extracts_text_and_chunks_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "agreement.pdf"
    document_writer = fitz.open()
    try:
        first_page = document_writer.new_page()
        first_page.insert_text(
            (72, 72),
            "1\nArticle 1. General provisions\nText of the first article.",
        )
        second_page = document_writer.new_page()
        second_page.insert_text(
            (72, 72),
            "Article 2. Review procedure\nText of the second article.",
        )
        document_writer.save(pdf_path)
    finally:
        document_writer.close()

    document = chunk_pdf(pdf_path, profile="generic")

    assert document.source_name == "agreement.pdf"
    assert document.profile == "generic"
    assert document.text == (
        "Article 1. General provisions\nText of the first article.\n\n"
        "Article 2. Review procedure\nText of the second article."
    )
    assert document.chunk_policy == "statute"
    assert [chunk.section_title for chunk in document.chunks] == [
        "Article 1. General provisions",
        "Article 2. Review procedure",
    ]


def test_chunk_pdf_preserves_guidance_policy_when_doc_kind_is_provided(tmp_path: Path) -> None:
    pdf_path = tmp_path / "guidance.pdf"
    document_writer = fitz.open()
    try:
        page = document_writer.new_page()
        page.insert_text(
            (72, 72),
            (
                "Review introduction.\n\n"
                "1. First review point.\n"
                "Point body.\n\n"
                "2. Second review point.\n"
                "Second body."
            ),
        )
        document_writer.save(pdf_path)
    finally:
        document_writer.close()

    document = chunk_pdf(pdf_path, profile="generic", doc_kind="court_guidance")

    assert document.chunk_policy == "guidance"
    assert [chunk.section_title for chunk in document.chunks] == [
        "Document",
        "Point 1",
        "Point 2",
    ]
    assert [chunk.chunk_method for chunk in document.chunks] == [
        "guidance_preamble",
        "guidance_point",
        "guidance_point",
    ]


def test_normalize_extracted_text_preserves_paragraph_boundaries() -> None:
    raw = "  Article 1.\r\n\r\nClause\u00A01 \n\n\nClause 2  "

    assert normalize_extracted_text(raw) == "Article 1.\n\nClause 1\n\nClause 2"


def test_normalize_chunk_text_collapses_whitespace() -> None:
    assert normalize_chunk_text("  A\n\nB\t C  ") == "A B C"


def test_semantic_hash_is_stable_for_whitespace_variants() -> None:
    first = compute_semantic_hash("Article 1.\n\nClause 1")
    second = compute_semantic_hash("  Article 1. Clause 1  ")

    assert first == second


def test_chunk_text_prefers_lower_statute_units_when_available() -> None:
    text = "\n".join(
        [
            "Article 1. General provisions",
            "Body of article one.",
            "1.1.1 Detailed rule",
            "Body of detailed rule.",
        ]
    )

    document = chunk_text(text, profile="generic", doc_kind="primary_legislation")

    assert document.chunk_policy == "statute"
    assert len(document.chunks) == 2
    assert [chunk.section_title for chunk in document.chunks] == [
        "Article 1. General provisions",
        "Section 1.1.1. Detailed rule",
    ]
    assert all(chunk.chunk_method == "statute_unit" for chunk in document.chunks)


def test_chunk_text_splits_guidance_root_into_multiple_chunks() -> None:
    text = "Intro paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    document = chunk_text(text, profile="generic", doc_kind="court_guidance")

    assert document.chunk_policy == "guidance"
    assert [chunk.text for chunk in document.chunks] == [
        "Intro paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]
    assert all(chunk.chunk_method == "guidance_preamble" for chunk in document.chunks)


def test_chunk_text_uses_char_fallback_for_oversized_paragraphs() -> None:
    oversized = "A" * 1305

    document = chunk_text(oversized, profile="generic", doc_kind="other")

    assert document.chunk_policy == "default"
    assert len(document.chunks) == 2
    assert [chunk.chunk_method for chunk in document.chunks] == ["char_fallback", "char_fallback"]


def test_chunk_text_preserves_preamble_before_first_heading() -> None:
    text = "\n".join(
        [
            "Introductory preamble text.",
            "Article 1. General provisions",
            "Body of article one.",
        ]
    )

    document = chunk_text(text, profile="generic", doc_kind="primary_legislation")

    assert document.chunk_policy == "statute"
    assert [chunk.section_title for chunk in document.chunks] == [
        "Document",
        "Article 1. General provisions",
    ]
    assert document.chunks[0].text == "Introductory preamble text."


def test_chunk_text_builds_guidance_point_chunks_from_review_fixture() -> None:
    text = (FIXTURES_DIR / "review_ru_guidance.txt").read_text(encoding="utf-8")

    document = chunk_text(text, profile="ru", doc_kind="court_guidance")

    assert document.chunk_policy == "guidance"
    assert [chunk.section_title for chunk in document.chunks] == [
        "Document",
        "Point 17",
        "Point 18",
    ]
    assert document.chunks[1].chunk_method == "guidance_point"
    assert document.chunks[1].section_type == "review_point"
    assert document.chunks[1].point_number == "17"
    assert document.chunks[1].legal_unit_type == "guidance_point"
    assert document.chunks[1].legal_unit_number == "17"
    assert document.chunks[1].source_case_number == "18-КГ23-155-К4"
    assert document.chunks[1].source_case_court == "Верховный Суд РФ"


def test_chunk_text_splits_oversized_guidance_point_by_paragraphs() -> None:
    oversized_text = "\n".join(
        [
            "Обзор судебной практики.",
            "",
            "17. Позиция суда о защите потребителя.",
            "A" * 700,
            "",
            "B" * 700,
        ]
    )

    document = chunk_text(oversized_text, profile="ru", doc_kind="court_guidance")

    assert document.chunk_policy == "guidance"
    assert [chunk.chunk_method for chunk in document.chunks] == [
        "guidance_preamble",
        "guidance_point_paragraph",
        "guidance_point_paragraph",
    ]
    point_chunks = [chunk for chunk in document.chunks if chunk.section_title == "Point 17"]
    assert len(point_chunks) == 2
    assert all(chunk.legal_unit_type == "guidance_point" for chunk in point_chunks)
    assert all(chunk.point_number == "17" for chunk in point_chunks)
