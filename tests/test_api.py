import json
from pathlib import Path

import fitz

from legal_chunking import chunk_pdf, chunk_text
from legal_chunking.cli import main as cli_main
from legal_chunking.detect.definitions import parse_definition_entries
from legal_chunking.detect.guidance_metadata import extract_guidance_point_metadata
from legal_chunking.detect.guidance_normalization import normalize_guidance_text
from legal_chunking.detect.headings import detect_heading
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

    document = chunk_pdf(pdf_path, profile="generic", trace=True)

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
    assert document.trace is not None
    pdf_events = [event for event in document.trace.events if event.type == "pdf_line_classified"]
    assert pdf_events
    assert pdf_events[0].stage == TraceStage.EXTRACT
    assert pdf_events[0].data["candidate_type"] == "PageNumberCandidate"
    assert pdf_events[0].data["rule_id"] == "pdf.line.page_number"
    decision_events = [event for event in document.trace.events if event.type == "pdf_line_decided"]
    assert decision_events
    assert decision_events[0].data["state_from"] == "front_matter"


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
    raw = "  Article 1.\r\n\r\nClause\u00a01 \n\n\nClause 2  "

    assert normalize_extracted_text(raw) == "Article 1.\n\nClause 1\n\nClause 2"


def test_normalize_chunk_text_collapses_whitespace() -> None:
    assert normalize_chunk_text("  A\n\nB\t C  ") == "A B C"


def test_semantic_hash_is_stable_for_whitespace_variants() -> None:
    first = compute_semantic_hash("Article 1.\n\nClause 1")
    second = compute_semantic_hash("  Article 1. Clause 1  ")

    assert first == second


def test_chunk_text_keeps_lower_statute_units_with_their_primary_article() -> None:
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
    assert len(document.chunks) == 1
    assert document.chunks[0].section_title == "Article 1. General provisions"
    assert "Body of article one." in document.chunks[0].text
    assert "1.1.1 Detailed rule" in document.chunks[0].text
    assert "Body of detailed rule." in document.chunks[0].text
    assert document.chunks[0].metadata.article_number == "1"
    assert len(document.sections) == 3
    assert all(chunk.chunk_method == "statute_unit" for chunk in document.chunks)


def test_chunk_text_keeps_unclassified_guidance_as_one_semantic_block() -> None:
    text = "Intro paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    document = chunk_text(text, profile="generic", doc_kind="court_guidance")

    assert document.chunk_policy == "guidance"
    assert [chunk.text for chunk in document.chunks] == [
        "Intro paragraph. Second paragraph. Third paragraph."
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
    assert document.chunks[1].metadata.point_number == "17"
    assert document.chunks[1].metadata.legal_unit_type == LegalUnitType.GUIDANCE_POINT
    assert document.chunks[1].metadata.legal_unit_number == "17"
    assert document.chunks[1].metadata.source_case_number == "18-КГ23-155-К4"
    assert document.chunks[1].metadata.source_case_court == "Верховный Суд РФ"


def test_normalize_guidance_text_recovers_inline_point_boundary_after_case_reference() -> None:
    raw = (
        "Предыдущая позиция суда. от 27 февраля 2024 г. № 5-КГ23-152-К2 7.\n"
        "Потребитель вправе требовать возмещения убытков."
    )

    normalized = normalize_guidance_text(raw)

    assert "№ 5-КГ23-152-К2\n7. Потребитель" in normalized


def test_extract_guidance_point_metadata_recovers_tail_case_reference() -> None:
    metadata = extract_guidance_point_metadata(
        (
            "17. Позиция суда по спору о страховании.\n"
            "Судебная коллегия по гражданским делам Верховного Суда РФ указала следующее.\n"
            "от 12 декабря 2023 г. № 18-КГ23-155-К4"
        ),
        point_number="17",
        profile="ru",
        doc_kind="court_guidance",
        extractor_scope="review_point",
    )

    assert metadata.source_case_reference == "от 12 декабря 2023 г. № 18-КГ23-155-К4"
    assert metadata.source_case_number == "18-КГ23-155-К4"
    assert metadata.source_case_date == "12 декабря 2023 г."
    assert metadata.source_case_court == "Верховный Суд РФ"


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
    assert all(
        chunk.metadata.legal_unit_type == LegalUnitType.GUIDANCE_POINT for chunk in point_chunks
    )
    assert all(chunk.metadata.point_number == "17" for chunk in point_chunks)


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
    assert point_chunks[0].metadata.source_case_number == "18-КГ23-155-К4"


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
    assert [chunk.metadata.legal_unit_type for chunk in document.chunks] == [
        None,
        LegalUnitType.RULE_BLOCK,
        LegalUnitType.RULE_BLOCK,
    ]
    assert [chunk.metadata.legal_unit_number for chunk in document.chunks] == [None, "1", "2"]
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
        "statute_unit",
        "definition_entry",
        "definition_entry",
    ]
    assert [chunk.metadata.legal_unit_type for chunk in document.chunks] == [
        None,
        LegalUnitType.DEFINITION_ENTRY,
        LegalUnitType.DEFINITION_ENTRY,
    ]
    assert [chunk.metadata.definition_term for chunk in document.chunks] == [
        None,
        "Client Money",
        "Sponsored VASP",
    ]
    assert [chunk.text for chunk in document.chunks] == [
        "Schedule 1 - Definitions Term Definition",
        '"Client Money" means money held on behalf of a client.',
        '"Sponsored VASP" means a VASP operating under a sponsorship arrangement.',
    ]
    assert " ".join(chunk.text for chunk in document.chunks) == " ".join(text.split())


def test_parse_definition_entries_keeps_alias_terms_and_quoted_definition_targets() -> None:
    text = (
        'Term Definition "Ultimate Beneficial Owner" or "UBO" '
        "has the meaning ascribed to it in the Company Rulebook. "
        '"VA Wallet" has the meaning ascribed to the term '
        '"Virtual Asset Wallet" in the Dubai VA Law. '
        '"Virtual Asset" or "VA" has the meaning ascribed to it in the Dubai VA Law.'
    )
    entries = parse_definition_entries(text)

    assert [entry.term for entry in entries] == [
        "Ultimate Beneficial Owner / UBO",
        "VA Wallet",
        "Virtual Asset / VA",
    ]
    assert entries[1].definition == (
        'has the meaning ascribed to the term "Virtual Asset Wallet" in the Dubai VA Law.'
    )


def test_detect_heading_prefers_explicit_part_after_roman_prefix() -> None:
    heading = detect_heading(
        "VII. Part VII – Sponsored VASPs",
        profile="ae",
        chunk_policy="statute",
    )

    assert heading is not None
    assert heading.kind == "part"
    assert heading.label == "Part VII. Sponsored VASPs"


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


def test_cli_chunk_outputs_chunks_only(capsys) -> None:
    exit_code = cli_main(
        [
            "chunk",
            "--text",
            "Article 1. General provisions\nBody of article one.",
            "--profile",
            "generic",
            "--doc-kind",
            "primary_legislation",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["chunk_policy"] == "statute"
    assert "sections" not in payload
    assert "trace" not in payload
    assert [chunk["section_title"] for chunk in payload["chunks"]] == [
        "Article 1. General provisions"
    ]


def test_cli_structure_outputs_sections_only(capsys) -> None:
    exit_code = cli_main(
        [
            "structure",
            "--text",
            "Part I - Compliance Management\nA. General principles\n1. Maintain controls.",
            "--profile",
            "ae",
            "--doc-kind",
            "primary_legislation",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "chunks" not in payload
    assert "trace" not in payload
    section_titles = [section["title"] for section in payload["sections"]]
    assert section_titles[:3] == [
        "Document",
        "Part I. Compliance Management",
        "Section A. General principles",
    ]
    assert "Section 1. Maintain controls." in section_titles


def test_cli_explain_outputs_trace_only(capsys) -> None:
    exit_code = cli_main(
        [
            "explain",
            "--text",
            "Part I - Compliance Management\nA. General principles\n1. Maintain controls.",
            "--profile",
            "ae",
            "--doc-kind",
            "primary_legislation",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "sections" not in payload
    assert "chunks" not in payload
    assert payload["trace"]["events"][0]["type"] == "chunk_policy_selected"
    assert payload["trace"]["events"][0]["stage"] == TraceStage.CHUNK


def test_cli_review_outputs_human_readable_chunk_previews(capsys) -> None:
    text = (
        "Article 1. General provisions\nBody of article one.\n\n"
        "Article 2. Scope\nBody of article two."
    )
    exit_code = cli_main(
        [
            "review",
            "--text",
            text,
            "--profile",
            "generic",
            "--doc-kind",
            "primary_legislation",
            "--limit",
            "2",
            "--max-chars",
            "40",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Source: <memory>" in output
    assert "Sections" in output
    assert "Chunks" in output
    assert "[1] Article 1. General provisions | kind=article" in output
    assert "method=statute_unit" in output
    assert "preview: Article 1. General provisions Body of a…" in output


def test_cli_review_writes_snapshot_to_output_file(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "snapshots" / "review.txt"

    exit_code = cli_main(
        [
            "review",
            "--text",
            "Point 1. Introductory guidance.\nPoint 2. Next guidance point.",
            "--profile",
            "ru",
            "--doc-kind",
            "court_guidance",
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    content = output_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert stdout == ""
    assert "Source: <memory>" in content
    assert "Chunks" in content
    assert "guidance_preamble" in content


def test_cli_chunk_writes_json_to_output_file(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "snapshots" / "chunks.json"

    exit_code = cli_main(
        [
            "chunk",
            "--text",
            "Article 1. General provisions\nBody of article one.",
            "--profile",
            "generic",
            "--doc-kind",
            "primary_legislation",
            "--output",
            str(output_path),
        ]
    )

    stdout = capsys.readouterr().out
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout == ""
    assert payload["chunk_policy"] == "statute"
    assert payload["chunks"][0]["section_title"] == "Article 1. General provisions"


def test_cli_chunk_reads_text_file_path(tmp_path: Path, capsys) -> None:
    text_path = tmp_path / "rulebook.txt"
    text_path.write_text(
        'Schedule 1 - Definitions\n"Client Money" means money held on behalf of a client.\n',
        encoding="utf-8",
    )

    exit_code = cli_main(
        [
            "chunk",
            "--path",
            str(text_path),
            "--profile",
            "ae",
            "--doc-kind",
            "primary_legislation",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["source_name"] == "rulebook.txt"
    assert payload["chunks"][0]["text"] == "Schedule 1 - Definitions"
    assert payload["chunks"][1]["metadata"]["definition_term"] == "Client Money"


def test_small_eu_preamble_is_not_lost_when_special_splitter_declines() -> None:
    document = chunk_text("Opening recital.\nArticle 1. Scope\nOperative provision.", profile="eu")
    assert document.chunks[0].text == "Opening recital."
    assert "Operative provision." in document.chunks[1].text


def test_guidance_offsets_use_the_document_text_plane() -> None:
    text = "Обзор судебной практики.\n\n1. Первый вывод.\n7\nТекст. 2.\nВторой вывод."
    document = chunk_text(text, profile="ru", doc_kind="court_guidance")
    assert [s.title for s in document.sections] == ["Document", "Point 1", "Point 2"]
    for section in document.sections:
        assert document.text[section.start_offset : section.end_offset] == section.text


def test_review_approval_directives_do_not_shadow_body_points() -> None:
    text = (
        "ПОСТАНОВЛЕНИЕ ПРЕЗИДИУМА\n1. Утвердить обзор.\n2. Определить порядок.\n"
        "ОБЗОР СУДЕБНОЙ ПРАКТИКИ\n1. Первый вывод.\n2. Второй вывод.\n3. Третий вывод."
    )
    document = chunk_text(text, profile="ru", doc_kind="court_guidance")
    assert [s.metadata.point_number for s in document.sections[1:]] == ["1", "2", "3"]
    assert "1. Утвердить обзор." in document.chunks[0].text
    assert document.chunks[1].text == "1. Первый вывод."


def test_statute_body_numbering_does_not_pop_article_context() -> None:
    document = chunk_text(
        "Статья 1. Общие положения\n1. Основное правило\nТекст правила.\n"
        "2. Второе правило\nСтатья 2. Заключение\nКонец.",
        profile="ru",
    )
    assert [s.metadata.article_number for s in document.sections[1:]] == ["1", "2"]
    assert len(document.chunks) == 2
    assert "2. Второе правило" in document.chunks[0].text
    assert "Статья 2" not in document.chunks[0].text


def test_native_pdf_preserves_raised_numbering_for_the_text_engine(tmp_path: Path) -> None:
    path = tmp_path / "raised.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_htmlbox(
            fitz.Rect(50, 50, 550, 200),
            "<p>Chapter 29<sup>1</sup>. Procedure</p>"
            "<p>Article 229<sup>5</sup>. Decision</p><p>Formula: 100<sup>2</sup>.</p>",
        )
        pdf.save(path)
    document = chunk_pdf(path, profile="ru")
    assert "Chapter 29.1" in document.text
    assert any(s.title == "Chapter 29.1. Procedure" for s in document.sections)
    assert any(s.metadata.article_number == "229.5" for s in document.sections)
    assert "100²" in document.text


def test_generic_normalization_preserves_spaced_separators() -> None:
    assert normalize_extracted_text("частью - Федеральный закон") == "частью - Федеральный закон"
    assert normalize_extracted_text("x - y") == "x - y"


def test_wrapped_case_identifier_preserves_its_hyphens() -> None:
    text = _normalize_page_raw_text("Ссылка № 5-КГ24-\n11-К2.", profile="ru")
    assert "5-КГ24-11-К2" in text


def test_statutory_instrument_is_not_source_case_metadata() -> None:
    metadata = extract_guidance_point_metadata(
        "1. Разъяснение. Постановление Правительства РФ от 2 апреля 2024 г. № 123.",
        point_number="1",
        profile="ru",
        doc_kind="court_guidance",
    )
    assert metadata.source_case_reference is None
    metadata = extract_guidance_point_metadata(
        "1. Вывод. Определение Верховного Суда РФ от 2 апреля 2024 г. № 5-КГ24-11-К2.",
        point_number="1",
        profile="ru",
        doc_kind="court_guidance",
    )
    assert metadata.source_case_number == "5-КГ24-11-К2"


def test_layout_backend_isolated_from_native_calls_and_cli_output(tmp_path: Path, capsys) -> None:
    path = tmp_path / "layout.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 90), "Article 1. Scope", fontsize=20)
        page.insert_text((72, 140), "This act applies to contracts.", fontsize=14)
        pdf.save(path)
    original = path.read_bytes()
    native = chunk_pdf(path, trace=True)
    layout = chunk_pdf(path, backend="pymupdf4llm", trace=True)
    assert [s.title for s in layout.sections] == ["Document", "Article 1. Scope"]
    assert layout.chunks[0].text == "Article 1. Scope This act applies to contracts."
    assert chunk_pdf(path, trace=True) == native
    assert path.read_bytes() == original
    event = next(e for e in layout.trace.events if e.type == "extraction_backend_selected")
    assert event.data["backend"] == "pymupdf4llm"
    assert event.data["ocr"] == "off"
    assert capsys.readouterr().out == ""
    assert cli_main(["chunk", "--path", str(path), "--backend", "pymupdf4llm"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["chunks"][0]["text"] == layout.chunks[0].text


def test_invalid_extraction_options_and_missing_ocr_data_fail_explicitly(
    tmp_path: Path, monkeypatch
) -> None:
    import pytest

    from legal_chunking import PdfDependencyError

    path = tmp_path / "options.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(path)
    for options in [
        {"backend": "unknown"},
        {"ocr": "auto"},
        {"ocr_dpi": 0},
        {"ocr_language": "../secret"},
        {"ocr": "unknown"},
    ]:
        with pytest.raises(ValueError):
            chunk_pdf(path, **options)
    monkeypatch.setenv("TESSDATA_PREFIX", str(tmp_path / "missing"))
    with pytest.raises(PdfDependencyError, match="traineddata"):
        chunk_pdf(path, backend="pymupdf4llm", ocr="force")


def test_each_chunk_has_a_boundary_trace_without_changing_output() -> None:
    text = "Article 1. Scope\nFirst body.\nArticle 2. Scope\nSecond body."
    traced = chunk_text(text, trace=True)
    plain = chunk_text(text)
    assert traced.chunks == plain.chunks
    events = [e for e in traced.trace.events if e.type == "chunk_created"]
    assert [e.data["chunk_id"] for e in events] == [c.chunk_id for c in traced.chunks]
    assert [e.data["section_id"] for e in events] == [c.section_id for c in traced.chunks]


def test_invalid_guidance_asset_is_not_silently_ignored(monkeypatch) -> None:
    from dataclasses import replace

    import pytest

    from legal_chunking import AssetConfigError
    from legal_chunking.detect import guidance_metadata
    from legal_chunking.profiles import resolve_profile

    broken = replace(resolve_profile("ru"), guidance_extractors={"candidate_patterns": "invalid"})
    guidance_metadata._load_guidance_metadata_config.cache_clear()
    monkeypatch.setattr(guidance_metadata, "resolve_profile", lambda profile: broken)
    with pytest.raises(AssetConfigError):
        extract_guidance_point_metadata("1. Вывод.", point_number="1", profile="ru")
