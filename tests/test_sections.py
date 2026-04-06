from pathlib import Path

from legal_chunking import assemble_sections, chunk_text
from legal_chunking.models import LegalUnitType

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_assemble_sections_returns_document_root_for_plain_text() -> None:
    sections = assemble_sections("Plain body text only.", profile="generic")

    assert len(sections) == 1
    assert sections[0].kind == "document_root"
    assert sections[0].title == "Document"
    assert sections[0].text == "Plain body text only."


def test_assemble_sections_builds_hierarchy_for_headings() -> None:
    text = "\n".join(
        [
            "Article 1. General provisions",
            "Body of article one.",
            "1.1 Scope",
            "Body of scope clause.",
        ]
    )

    sections = assemble_sections(text, profile="generic")

    assert len(sections) == 3
    assert sections[0].kind == "document_root"
    assert sections[1].kind == "article"
    assert sections[1].metadata.article_number == "1"
    assert sections[1].parent_section_id == sections[0].section_id
    assert sections[2].kind == "article"
    assert sections[2].metadata.article_number == "1.1"
    assert sections[2].parent_section_id == sections[0].section_id


def test_chunk_text_materializes_sections_and_section_chunks() -> None:
    text = "\n".join(
        [
            "Article 1. General provisions",
            "Body of article one.",
            "Article 2. Final provisions",
            "Body of article two.",
        ]
    )

    document = chunk_text(text, profile="generic")

    assert len(document.sections) == 3
    assert [chunk.section_title for chunk in document.chunks] == [
        "Article 1. General provisions",
        "Article 2. Final provisions",
    ]
    assert document.chunks[0].prev_chunk_id is None
    assert document.chunks[-1].next_chunk_id is None


def test_repeated_heading_paths_get_distinct_section_ids() -> None:
    text = "\n".join(
        [
            "Article 1. Same",
            "First body.",
            "Article 1. Same",
            "Second body.",
        ]
    )

    sections = assemble_sections(text, profile="generic")

    assert len(sections) == 3
    assert sections[1].section_id != sections[2].section_id
    assert sections[1].text.endswith("First body.")
    assert sections[2].text.endswith("Second body.")


def test_noncanonical_other_heading_is_promoted_to_root_level() -> None:
    text = "\n".join(
        [
            "Article 1. Main section",
            "Body of main section.",
            "Schedule No. 1 Definitions",
            "Body of schedule.",
        ]
    )

    sections = assemble_sections(text, profile="generic")

    assert len(sections) == 3
    assert sections[2].kind == "other"
    assert sections[2].parent_section_id == sections[0].section_id
    assert sections[2].title == "Schedule 1. Definitions"


def test_assemble_sections_builds_guidance_point_sections_from_ru_review_fixture() -> None:
    text = (FIXTURES_DIR / "review_ru_guidance.txt").read_text(encoding="utf-8")

    sections = assemble_sections(
        text,
        profile="ru",
        chunk_policy="guidance",
        doc_kind="court_guidance",
    )

    assert [section.title for section in sections] == ["Document", "Point 17", "Point 18"]
    assert sections[0].section_type == "document_root"
    assert sections[0].text == "Обзор судебной практики по делам о защите прав потребителей."
    assert sections[1].section_type == "review_point"
    assert sections[1].metadata.legal_unit_type == LegalUnitType.GUIDANCE_POINT
    assert sections[1].metadata.point_number == "17"
    assert sections[1].metadata.legal_unit_number == "17"
    assert sections[1].metadata.source_case_reference is not None
    assert sections[1].metadata.source_case_number == "18-КГ23-155-К4"
    assert sections[1].metadata.source_case_date == "12 декабря 2023 г."
    assert sections[1].metadata.source_case_court == "Верховный Суд РФ"


def test_assemble_sections_from_us_rule_fixture() -> None:
    text = (FIXTURES_DIR / "us_rule_example.txt").read_text(encoding="utf-8")
    sections = assemble_sections(text, profile="us")

    # The fixture starts with "Rule 4. Summons"
    assert any(s.kind == "article" and "Rule 4" in (s.title or "") for s in sections)


def test_assemble_sections_from_eu_statute_fixture() -> None:
    text = (FIXTURES_DIR / "eu_statute_example.txt").read_text(encoding="utf-8")
    sections = assemble_sections(text, profile="eu")

    assert any(s.kind == "article" and "Article 12" in (s.title or "") for s in sections)


def test_assemble_sections_from_ae_rulebook_fixture() -> None:
    text = (FIXTURES_DIR / "ae_rule_example.txt").read_text(encoding="utf-8")
    sections = assemble_sections(text, profile="ae", doc_kind="primary_legislation")

    assert any(s.kind == "section" and "Section A" in (s.title or "") for s in sections)
