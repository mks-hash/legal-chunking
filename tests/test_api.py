from pathlib import Path

import fitz

from legal_chunking import chunk_pdf, chunk_text
from legal_chunking.extract.pdf import (
    _find_repeated_leading_header_fingerprints,
    _find_repeated_page_noise,
    _normalize_page_raw_text,
)
from legal_chunking.hashing import compute_semantic_hash
from legal_chunking.models import LegalUnitType
from legal_chunking.normalize import normalize_chunk_text, normalize_extracted_text
from legal_chunking.tracing import TraceStage

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
    assert document.trace is None


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


def test_chunk_pdf_cleans_toc_noise_and_detects_uae_rulebook_sections(tmp_path: Path) -> None:
    pdf_path = tmp_path / "vara-rulebook.pdf"
    document_writer = fitz.open()
    try:
        first_page = document_writer.new_page()
        first_page.insert_text(
            (72, 72),
            (
                "header@vara.ae - Virtual Assets Regulatory Authority\n"
                "Contents\n"
                "I.\n"
                "PART I - COMPLIANCE MANAGEMENT ................................ 6\n"
                "A.\n"
                "General principles ................................ 6\n"
            ),
        )
        second_page = document_writer.new_page()
        second_page.insert_text(
            (72, 72),
            (
                "header@vara.ae - Virtual Assets Regulatory Authority\n"
                "Introduction\n"
                "This Rulebook is issued by VARA.\n"
                "I.\n"
                "Part I - Compliance Management\n"
                "A.\n"
                "General principles\n"
                "Licensed entities must maintain controls.\n"
                "B.\n"
                "Compliance management system\n"
                "Firms must document their framework.\n"
            ),
        )
        document_writer.save(pdf_path)
    finally:
        document_writer.close()

    document = chunk_pdf(pdf_path, profile="ae", doc_kind="primary_legislation")

    assert document.profile == "ae"
    assert document.chunk_policy == "statute"
    assert "Contents" not in document.text
    assert "................................" not in document.text
    assert "header@vara.ae" not in document.text
    assert [section.title for section in document.sections] == [
        "Document",
        "Part I. Compliance Management",
        "Section A. General principles",
        "Section B. Compliance management system",
    ]
    assert [chunk.section_title for chunk in document.chunks] == [
        "Document",
        "Part I. Compliance Management",
        "Section A. General principles",
        "Section B. Compliance management system",
    ]


def test_normalize_page_raw_text_keeps_single_lowercase_content_line() -> None:
    raw = "\n".join(
        [
            "a",
            "Borrower obligations continue after this broken marker line.",
        ]
    )

    normalized = _normalize_page_raw_text(raw, profile="generic")

    assert normalized == "a Borrower obligations continue after this broken marker line."


def test_normalize_page_raw_text_preserves_non_header_arabic_content() -> None:
    raw = "\n".join(
        [
            "دبي market participants must comply with the applicable rulebook.",
            "Article 1. General provisions",
        ]
    )

    normalized = _normalize_page_raw_text(raw, profile="generic")

    assert normalized.startswith("دبي market participants")
    assert "Article 1. General provisions" in normalized


def test_normalize_page_raw_text_does_not_drop_marker_without_repetition() -> None:
    raw = "\n".join(
        [
            "Virtual Assets Regulatory Authority licensing conditions apply.",
            "Article 1. General provisions",
        ]
    )

    normalized = _normalize_page_raw_text(raw, profile="generic")

    assert normalized.startswith("Virtual Assets Regulatory Authority licensing conditions apply.")
    assert "Article 1. General provisions" in normalized


def test_normalize_page_raw_text_trims_repeated_leading_header_noise() -> None:
    raw = "\n".join(
        [
            "Virtual Assets Regulatory Authority",
            "Article 1. General provisions",
            "Body of article one.",
        ]
    )

    normalized = _normalize_page_raw_text(
        raw,
        profile="generic",
        repeated_noise={"Virtual Assets Regulatory Authority"},
    )

    assert normalized == "Article 1. General provisions\nBody of article one."


def test_find_repeated_page_noise_keeps_short_repeated_headers_but_not_rule_markers() -> None:
    repeated_noise = _find_repeated_page_noise(
        [
            ["araconnect@vara.ae", ":صندوق بريد9292", "دبي، اإلمارات العربية المتحدة -", "1."],
            ["araconnect@vara.ae", ":صندوق بريد9292", "دبي، اإلمارات العربية المتحدة -", "2."],
            ["araconnect@vara.ae", ":صندوق بريد9292", "دبي، اإلمارات العربية المتحدة -", "3."],
        ]
    )

    assert "araconnect@vara.ae" in repeated_noise
    assert ":صندوق بريد9292" in repeated_noise
    assert "دبي، اإلمارات العربية المتحدة -" in repeated_noise
    assert "1." not in repeated_noise


def test_find_repeated_leading_header_fingerprints_normalizes_repeated_variants() -> None:
    fingerprints = _find_repeated_leading_header_fingerprints(
        [
            ["v سُلطة تنظيم", "األصول االفتراضية", "Article 1. General provisions"],
            ["x سلطة تنظيم", "الأصول الافتراضية", "Article 2. General provisions"],
            ["z سلطة تنظيم", "الأصول الافتراضية", "Article 3. General provisions"],
        ]
    )

    assert "سلطة تنظيم" in fingerprints


def test_normalize_page_raw_text_keeps_enumerated_content_outside_heading_detection() -> None:
    raw = "\n".join(
        [
            "Section A. General principles",
            "1. Licensed entities must maintain effective controls.",
            "2. Licensed entities must maintain independent oversight.",
        ]
    )

    normalized = _normalize_page_raw_text(raw, profile="ae")

    assert normalized == "\n".join(
        [
            "Section A. General principles",
            "1. Licensed entities must maintain effective controls.",
            "2. Licensed entities must maintain independent oversight.",
        ]
    )


def test_normalize_page_raw_text_drops_contextual_junk_prefix_before_header() -> None:
    raw = "\n".join(
        [
            "v",
            "سُلطة تنظيم",
            "األصول االفتراضية",
            "Article 1. General provisions",
        ]
    )

    normalized = _normalize_page_raw_text(
        raw,
        profile="generic",
        repeated_fingerprints={"سلطة تنظيم", "األصول االفتراضية"},
    )

    assert normalized == "Article 1. General provisions"


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
    assert document.chunks[1].legal_unit_type == LegalUnitType.GUIDANCE_POINT
    assert document.chunks[1].legal_unit_number == "17"
    assert document.chunks[1].source_case_number == "18-КГ23-155-К4"
    assert document.chunks[1].source_case_court == "Верховный Суд РФ"


def test_chunk_text_keeps_oversized_guidance_point_as_single_chunk() -> None:
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
        "guidance_point",
    ]
    point_chunks = [chunk for chunk in document.chunks if chunk.section_title == "Point 17"]
    assert len(point_chunks) == 1
    assert all(chunk.legal_unit_type == LegalUnitType.GUIDANCE_POINT for chunk in point_chunks)
    assert all(chunk.point_number == "17" for chunk in point_chunks)


def test_chunk_text_keeps_realistic_guidance_fixture_points_as_primary_units() -> None:
    text = (FIXTURES_DIR / "review_ru_guidance.txt").read_text(encoding="utf-8")
    expanded_text = text.replace(
        "17. Банк как выгодоприобретатель по договору личного страхования.",
        (
            "17. Банк как выгодоприобретатель по договору личного страхования.\n"
            + "\n".join(["Дополнительное обоснование позиции суда."] * 80)
        ),
    )

    document = chunk_text(expanded_text, profile="ru", doc_kind="court_guidance")

    assert document.chunk_policy == "guidance"
    assert [chunk.section_title for chunk in document.chunks] == [
        "Document",
        "Point 17",
        "Point 18",
    ]
    point_chunks = [chunk for chunk in document.chunks if chunk.section_title == "Point 17"]
    assert len(point_chunks) == 1
    assert point_chunks[0].chunk_method == "guidance_point"
    assert point_chunks[0].source_case_number == "18-КГ23-155-К4"


def test_chunk_text_splits_oversized_uae_rulebook_section_by_numbered_rules() -> None:
    text = "\n".join(
        [
            "Part I - Compliance Management",
            "A. General principles",
            "1.",
            " ".join(["Licensed entities must maintain effective controls."] * 20),
            "2.",
            " ".join(["Licensed entities must maintain independent oversight."] * 20),
        ]
    )

    document = chunk_text(text, profile="ae", doc_kind="primary_legislation")

    assert document.chunk_policy == "statute"
    assert [chunk.chunk_method for chunk in document.chunks] == [
        "statute_unit",
        "statute_rule",
        "statute_rule",
    ]
    assert [chunk.section_title for chunk in document.chunks] == [
        "Part I. Compliance Management",
        "Section A. General principles",
        "Section A. General principles",
    ]
    assert [chunk.legal_unit_type for chunk in document.chunks] == [
        None,
        LegalUnitType.RULE_BLOCK,
        LegalUnitType.RULE_BLOCK,
    ]
    assert [chunk.legal_unit_number for chunk in document.chunks] == [None, "1", "2"]
    assert document.chunks[1].text.startswith("Section A. General principles 1.")
    assert document.chunks[2].text.startswith("Section A. General principles 2.")


def test_chunk_text_splits_definition_schedule_into_definition_entries() -> None:
    text = "\n".join(
        [
            "Schedule 1 - Definitions",
            "Term Definition",
            '"Client Money" means money held on behalf of a client.',
            '"Sponsored VASP" means a VASP operating under a sponsorship arrangement.',
        ]
    )

    document = chunk_text(text, profile="ae", doc_kind="primary_legislation")

    assert document.chunk_policy == "statute"
    assert [chunk.chunk_method for chunk in document.chunks] == [
        "definition_entry",
        "definition_entry",
    ]
    assert [chunk.legal_unit_type for chunk in document.chunks] == [
        LegalUnitType.DEFINITION_ENTRY,
        LegalUnitType.DEFINITION_ENTRY,
    ]
    assert [chunk.definition_term for chunk in document.chunks] == [
        "Client Money",
        "Sponsored VASP",
    ]
    assert document.chunks[0].text.startswith("Client Money:")
    assert document.chunks[1].text.startswith("Sponsored VASP:")


def test_chunk_text_trace_reports_structure_and_chunk_decisions() -> None:
    text = "\n".join(
        [
            "Part I - Compliance Management",
            "A. General principles",
            "1.",
            " ".join(["Licensed entities must maintain effective controls."] * 20),
            "2.",
            " ".join(["Licensed entities must maintain independent oversight."] * 20),
        ]
    )

    document = chunk_text(text, profile="ae", doc_kind="primary_legislation", trace=True)

    assert document.trace is not None
    event_types = [event.type for event in document.trace.events]
    assert event_types[:2] == ["chunk_policy_selected", "document_normalized"]
    assert document.trace.events[0].stage == TraceStage.CHUNK
    assert document.trace.events[1].stage == TraceStage.NORMALIZE
    assert "heading_detected" in event_types
    assert "rule_block_split" in event_types
    rule_split_event = next(
        event for event in document.trace.events if event.type == "rule_block_split"
    )
    assert rule_split_event.stage == TraceStage.CHUNK
    assert rule_split_event.data == {
        "section": "Section A. General principles",
        "count": 2,
    }
