from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from legal_chunking import chunk_pdf, extract_references

TESTINGS_DIR = Path(__file__).resolve().parents[1] / ".develop" / "testings"


def _require_testing_pdf(name: str) -> Path:
    path = TESTINGS_DIR / name
    if not path.exists():
        pytest.skip(f"Real PDF fixture is missing: {path}")
    return path


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_real_pdf_gdpr_eu_statute_structure() -> None:
    path = _require_testing_pdf("CELEX_32016R0679_EN_TXT.pdf")

    document = chunk_pdf(path, profile="eu")
    section_titles = [section.title for section in document.sections]
    article_titles = [title for title in section_titles if title.startswith("Article ")]
    chunk_methods = Counter(chunk.chunk_method for chunk in document.chunks)
    article_12_methods = {
        chunk.chunk_method for chunk in document.chunks if chunk.section_title == "Article 12"
    }
    article_32_methods = {
        chunk.chunk_method for chunk in document.chunks if chunk.section_title == "Article 32"
    }

    assert document.profile == "eu"
    assert document.chunk_policy == "statute"
    assert len(document.sections) >= 120
    assert len(document.chunks) >= 350
    assert "REGULATION (EU) 2016/679" in _collapse_ws(document.text)
    assert section_titles[:8] == [
        "Document",
        "Chapter I",
        "Article 1",
        "Article 2",
        "Article 3",
        "Article 4",
        "Chapter II",
        "Article 5",
    ]
    assert article_titles[:12] == [f"Article {index}" for index in range(1, 13)]
    assert "Article 4" in section_titles
    assert not any(title.startswith("Article 263") for title in article_titles)
    assert not any(title.startswith("Section L.") for title in section_titles[:20])
    assert "Section M. SCHULZ" not in section_titles
    assert chunk_methods["statute_unit"] > chunk_methods["char_fallback"]
    assert article_12_methods == {"statute_unit"}
    assert article_32_methods == {"statute_unit"}


def test_real_pdf_frcp_us_extracts_text_and_usc_references() -> None:
    path = _require_testing_pdf("federal-rules-of-civil-procedure-dec-1-2024_0.pdf")

    document = chunk_pdf(path, profile="us")
    references = extract_references(document.text[:5000], profile="us")
    section_titles = [section.title for section in document.sections]
    chunk_methods = Counter(chunk.chunk_method for chunk in document.chunks)

    assert document.profile == "us"
    assert document.chunk_policy == "statute"
    assert len(document.sections) >= 100
    assert len(document.chunks) >= 350
    assert "FEDERAL RULES OF CIVIL PROCEDURE" in _collapse_ws(document.text)
    assert "Rule 1. Scope" in document.text
    assert section_titles[:7] == [
        "Document",
        "Part I. SCOPE OF RULES; FORM OF ACTION",
        "Rule 1. Scope and Purpose",
        "Rule 2. One Form of Action",
        "Part II. COMMENCING AN ACTION; SERVICE OF PROCESS,",
        "Rule 3. Commencing an Action",
        "Rule 4. Summons",
    ]
    assert "Section CIVIL. PROCEDURE" not in section_titles[:10]
    assert "Part 28. , UNITED STATES CODE" not in section_titles[:10]
    assert "Rule 4" not in section_titles
    assert "Rule 12" not in section_titles
    assert "Rule 14" not in section_titles
    assert (
        "Rule 5.1. Constitutional Challenge to a Statute—Notice, Certification, and Intervention"
        in section_titles
    )
    assert (
        "Rule 11. Signing Pleadings, Motions, and Other Papers; "
        "Representations to the Court; Sanctions" in section_titles
    )
    assert not any(title.startswith("Section 20.") for title in section_titles)
    assert not any(title.startswith("Paragraph 2403") for title in section_titles)
    assert not any(title.startswith("Paragraph 1332") for title in section_titles)
    assert chunk_methods["statute_unit"] >= 300
    assert chunk_methods["char_fallback"] <= 80
    assert ("section", "1915", "usc") in {
        (ref.scheme, ref.article_number, ref.doc_family) for ref in references
    }
    assert ("section", "1916.", "usc") in {
        (ref.scheme, ref.article_number, ref.doc_family) for ref in references
    }


def test_real_pdf_vara_rulebook_detects_rulebook_sections_and_special_chunking() -> None:
    path = _require_testing_pdf("VARA_EN_123_VER20250519.pdf")

    document = chunk_pdf(path, profile="ae", doc_kind="primary_legislation")

    section_titles = {section.title for section in document.sections}
    chunk_methods = {chunk.chunk_method for chunk in document.chunks}
    document_chunks = [chunk for chunk in document.chunks if chunk.section_title == "Document"]

    assert document.profile == "ae"
    assert document.chunk_policy == "statute"
    assert len(document.sections) >= 40
    assert len(document.chunks) >= 150
    assert "Part I. Compliance Management" in section_titles
    assert "Section A. General principles" in section_titles
    assert "Section B. Compliance management system" in section_titles
    assert "statute_rule" in chunk_methods
    assert "definition_entry" in chunk_methods
    assert document_chunks
    assert {chunk.chunk_method for chunk in document_chunks} == {"statute_unit"}
    assert document_chunks[0].text.startswith("Introduction The Dubai Virtual Assets")
    assert all(
        chunk.text != "Compliance and Risk Management Rulebook 19 May 2025"
        for chunk in document_chunks
    )


def test_real_pdf_ru_consumer_review_detects_guidance_points() -> None:
    path = _require_testing_pdf(
        "Обзор-судебной-практики-по-делам-о-защите-прав-потребителей-от-23-октября-2024.pdf"
    )

    document = chunk_pdf(path, profile="ru", doc_kind="court_guidance")

    section_titles = [section.title for section in document.sections]
    chunk_methods = {chunk.chunk_method for chunk in document.chunks}
    point_numbers = [chunk.metadata.point_number for chunk in document.chunks[1:]]
    case_references = [chunk.metadata.source_case_reference for chunk in document.chunks[1:8]]

    assert document.profile == "ru"
    assert document.chunk_policy == "guidance"
    assert len(document.sections) == 25
    assert len(document.sections) == len(document.chunks)
    assert section_titles[:10] == [
        "Document",
        "Point 1",
        "Point 2",
        "Point 3",
        "Point 4",
        "Point 5",
        "Point 6",
        "Point 7",
        "Point 8",
        "Point 9",
    ]
    assert section_titles[-5:] == [
        "Point 20",
        "Point 21",
        "Point 22",
        "Point 23",
        "Point 24",
    ]
    assert chunk_methods == {"guidance_preamble", "guidance_point"}
    assert document.chunks[0].chunk_method == "guidance_preamble"
    assert document.chunks[0].metadata.point_number is None
    assert point_numbers == [str(index) for index in range(1, 25)]
    assert case_references == [
        "от 28 ноября 2023 г. № 44-КГ23-24-К7",
        "от 2 апреля 2024 г. № 5-КГ24-11-К2",
        "от 25 июня 2024 г. № 49-КГ24-6-К6",
        "от 5 марта 2024 г. № 5-КГ23-158-К2",
        "от 23 января 2024 г. № 46-КГ23-15-К6",
        "от 27 февраля 2024 г. № 5-КГ23-152-К2",
        "от 3 октября 2023 г. № 16-КГ23-44-К4",
    ]


def test_real_pdf_ru_plenum_detects_large_guidance_structure() -> None:
    path = _require_testing_pdf(
        "Постановление-Пленума-Верховного-Суда-Российской-Федерации-от-23-апреля-2019-N-10.pdf"
    )

    document = chunk_pdf(path, profile="ru", doc_kind="court_guidance")

    section_titles = [section.title for section in document.sections]
    chunk_methods = {chunk.chunk_method for chunk in document.chunks}
    point_numbers = [chunk.metadata.point_number for chunk in document.chunks[1:]]
    case_references = {chunk.metadata.source_case_reference for chunk in document.chunks}

    assert document.profile == "ru"
    assert document.chunk_policy == "guidance"
    assert len(document.sections) == 183
    assert len(document.sections) == len(document.chunks)
    assert section_titles[:10] == [
        "Document",
        "Point 1",
        "Point 2",
        "Point 3",
        "Point 4",
        "Point 5",
        "Point 6",
        "Point 7",
        "Point 8",
        "Point 9",
    ]
    assert section_titles[-5:] == [
        "Point 178",
        "Point 179",
        "Point 180",
        "Point 181",
        "Point 182",
    ]
    assert chunk_methods == {"guidance_preamble", "guidance_point"}
    assert document.chunks[0].chunk_method == "guidance_preamble"
    assert document.chunks[0].metadata.point_number is None
    assert point_numbers == [str(index) for index in range(1, 183)]
    assert {
        "постановление Пленума Верховного Суда Российской Федерации от 19 июня 2006 года № 15",
        "постановление Пленума Верховного Суда Российской Федерации от 29 мая 2012 года № 9",
        (
            "постановление Пленума Верховного Суда Российской Федерации и "
            "Пленума Высшего Арбитражного Суда Российской Федерации от 26 "
            "марта 2009 года № 5/29"
        ),
        "постановление Пленума Верховного Суда СССР от 15 ноября 1984 года № 22",
    } <= case_references


def test_real_pdf_apk_preserves_numbered_article_bodies_and_raised_chapter() -> None:
    path = _require_testing_pdf("АПК РФ актуальная редакция от 01.01.2026.pdf")
    document = chunk_pdf(path, profile="ru", doc_kind="code")
    chapters = [s.title for s in document.sections if s.kind == "chapter"]
    assert any(title.startswith("Chapter 29.1. ПРИКАЗНОЕ") for title in chapters)
    assert not any(title.startswith("Chapter 291.") for title in chapters)
    article_three = next(s for s in document.sections if s.metadata.article_number == "3")
    assert "В соответствии с Конституцией Российской Федерации" in article_three.text
    assert any(
        c.section_id == article_three.section_id
        and "В соответствии с Конституцией Российской Федерации" in c.text
        for c in document.chunks
    )
    assert any(s.metadata.article_number == "229.5" for s in document.sections)
    assert not any(s.title.startswith("Section 1. В соответствии") for s in document.sections)


def test_real_pdf_review_2026_excludes_approval_directives_from_point_sequence() -> None:
    path = _require_testing_pdf(
        "Обзор судебной практики Верховного Суда Российской Федерации № 2 (2026).pdf"
    )
    document = chunk_pdf(path, profile="ru", doc_kind="court_guidance")
    assert [s.metadata.point_number for s in document.sections[1:]] == [
        str(n) for n in range(1, 53)
    ]
    assert len(document.chunks) == 53
    assert "Утвердить Обзор" in document.chunks[0].text
    assert "К требованию об исключении земельного участка" in document.chunks[1].text
    assert document.chunks[-1].metadata.point_number == "52"


def test_scanned_pdf_ocr_is_repeatable_quiet_and_preserves_source(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    import json

    import pymupdf

    from legal_chunking.cli import main

    data = TESTINGS_DIR / "ocr-data"
    if not (data / "eng.traineddata").exists():
        pytest.skip("Local Tesseract English traineddata is missing")
    monkeypatch.setenv("TESSDATA_PREFIX", str(data))
    source = tmp_path / "scan.pdf"
    with pymupdf.open() as native:
        page = native.new_page()
        page.insert_text((72, 90), "Article 1. Scope", fontsize=20)
        page.insert_text((72, 140), "This act applies to contracts.", fontsize=14)
        image = page.get_pixmap(dpi=150).tobytes("png")
    with pymupdf.open() as scanned:
        scanned.new_page()  # Blank pages must not break forced OCR or renumber later pages.
        scanned.new_page().insert_image(pymupdf.Rect(0, 0, 595, 842), stream=image)
        scanned.save(source)
    original = source.read_bytes()
    assert chunk_pdf(source).text == ""
    document = chunk_pdf(source, backend="pymupdf4llm", ocr="force", ocr_dpi=180, trace=True)
    assert document.text == "Article 1. Scope\nThis act applies to contracts."
    assert (
        chunk_pdf(source, backend="pymupdf4llm", ocr="force", ocr_dpi=180, trace=True) == document
    )
    assert original == source.read_bytes()
    events = [e for e in document.trace.events if e.type == "ocr_page_processed"]
    assert any(e.data["page_number"] == 2 and e.data["dpi"] == 180 for e in events)
    configuration = next(e for e in document.trace.events if e.type == "ocr_configuration")
    assert len(configuration.data["model_hashes"]["eng"]) == 64
    assert capsys.readouterr().out == ""
    assert (
        main(
            [
                "explain",
                "--path",
                str(source),
                "--backend",
                "pymupdf4llm",
                "--ocr",
                "force",
                "--ocr-dpi",
                "180",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["trace"]["events"]
