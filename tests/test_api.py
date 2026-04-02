from legal_chunking import chunk_pdf, chunk_text
from legal_chunking.hashing import compute_semantic_hash
from legal_chunking.normalize import normalize_chunk_text, normalize_extracted_text


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


def test_chunk_pdf_returns_placeholder_document() -> None:
    document = chunk_pdf("agreement.pdf", profile="ru")

    assert document.source_name == "agreement.pdf"
    assert document.profile == "ru"
    assert document.chunks == []
    assert document.chunk_policy == "statute"


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
    assert all(chunk.chunk_method == "guidance_block" for chunk in document.chunks)


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
