from legal_chunking import chunk_pdf, chunk_text


def test_chunk_text_returns_document() -> None:
    document = chunk_text("  Article 1. Test clause  ")

    assert document.profile == "generic"
    assert document.text == "Article 1. Test clause"
    assert len(document.chunks) == 1
    assert document.chunks[0].text == "Article 1. Test clause"


def test_chunk_pdf_returns_placeholder_document() -> None:
    document = chunk_pdf("agreement.pdf", profile="ru")

    assert document.source_name == "agreement.pdf"
    assert document.profile == "ru"
    assert document.chunks == []
