import pytest

from legal_chunking.detect.headings import compile_heading_patterns, detect_heading


def test_compile_heading_patterns_for_ru_profile() -> None:
    patterns = compile_heading_patterns("ru")

    assert patterns
    assert any(section_type == "article" for section_type, _pattern in patterns)


def test_detect_article_heading_for_ru_profile() -> None:
    heading = detect_heading("Статья 12. Порядок рассмотрения", profile="ru")

    assert heading is not None
    assert heading.kind == "article"
    assert heading.article_number == "12"
    assert heading.label == "Article 12. Порядок рассмотрения"


def test_detect_numeric_heading_maps_to_article_when_nested() -> None:
    heading = detect_heading("1.2 Scope and purpose", profile="generic")

    assert heading is not None
    assert heading.kind == "article"
    assert heading.article_number == "1.2"
    assert heading.label == "Section 1.2. Scope and purpose"


def test_detect_numeric_heading_maps_to_section_when_top_level() -> None:
    heading = detect_heading("1. Scope and purpose", profile="generic")

    assert heading is not None
    assert heading.kind == "section"
    assert heading.article_number is None
    assert heading.label == "Section 1. Scope and purpose"


@pytest.mark.parametrize(
    "line",
    [
        "1 this line should stay body text",
        "2024 Revenue increased across the portfolio",
    ],
)
def test_reject_non_heading_numeric_line(line: str) -> None:
    heading = detect_heading(line, profile="generic")

    assert heading is None


def test_guidance_policy_rejects_article_like_headings() -> None:
    heading = detect_heading(
        "Article 5. Review standard",
        profile="generic",
        chunk_policy="guidance",
    )

    assert heading is None


def test_guidance_policy_rejects_numeric_article_like_headings() -> None:
    heading = detect_heading(
        "1.2 Scope and purpose",
        profile="generic",
        chunk_policy="guidance",
    )

    assert heading is None


def test_detect_schedule_as_noncanonical_other() -> None:
    heading = detect_heading("Schedule A. Definitions", profile="generic")

    assert heading is not None
    assert heading.kind == "other"
    assert heading.label == "Schedule A. Definitions"


def test_detect_schedule_number_with_no_marker() -> None:
    heading = detect_heading("Schedule No. 1 Definitions", profile="generic")

    assert heading is not None
    assert heading.kind == "other"
    assert heading.label == "Schedule 1. Definitions"
