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
    assert document.chunks[0].prev_chunk_id is None
    assert document.chunks[0].next_chunk_id is None
    assert document.pipeline_version == "0.1.0"


def test_chunk_pdf_returns_placeholder_document() -> None:
    document = chunk_pdf("agreement.pdf", profile="ru")

    assert document.source_name == "agreement.pdf"
    assert document.profile == "ru"
    assert document.chunks == []
    assert document.pipeline_version == "0.1.0"


def test_normalize_extracted_text_preserves_paragraph_boundaries() -> None:
    raw = "  Article 1.\r\n\r\nClause\u00A01 \n\n\nClause 2  "

    assert normalize_extracted_text(raw) == "Article 1.\n\nClause 1\n\nClause 2"


def test_normalize_chunk_text_collapses_whitespace() -> None:
    assert normalize_chunk_text("  A\n\nB\t C  ") == "A B C"


def test_semantic_hash_is_stable_for_whitespace_variants() -> None:
    first = compute_semantic_hash("Article 1.\n\nClause 1")
    second = compute_semantic_hash("  Article 1. Clause 1  ")

    assert first == second
