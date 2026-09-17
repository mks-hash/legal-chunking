"""Source anchors survive actual repairs and preserve repeated citation occurrences."""

from dataclasses import asdict

import pytest

from legal_chunking import ReferenceAnalysis, extract_references
from legal_chunking import analyze_references as analyze


def check_spans(text: str, result: ReferenceAnalysis) -> None:
    for occurrence in result.occurrences:
        assert text[occurrence.start_offset : occurrence.end_offset] == occurrence.raw
        assert 0 <= occurrence.start_offset < occurrence.end_offset <= len(text)
        normalized = result.normalized_text[
            occurrence.normalized_start_offset : occurrence.normalized_end_offset
        ]
        assert all(ref.raw == normalized for ref in occurrence.references)
        assert occurrence.references


def test_repeated_citations_have_distinct_source_anchors_without_legacy_duplicates() -> None:
    text = "статья 450 ГК РФ; снова статья 450 ГК РФ"
    result = analyze(text, profile="ru")
    assert len(result.occurrences) == 2
    first, second = result.occurrences
    assert first.raw == second.raw == "статья 450"
    assert first.start_offset == 0
    assert second.start_offset == text.index("статья", 1)
    assert first.references == second.references
    assert len(extract_references(text, profile="ru")) == 1
    check_spans(text, result)


@pytest.mark.parametrize(
    "source,raw,number",
    [
        ("😀 начало; статья\u00a0229⁵ АПК РФ", "статья\u00a0229⁵", "229.5"),
        ("статья 225¹⁶⁻¹ АПК РФ", "статья 225¹⁶⁻¹", "225.16-1"),
        ("статья 2295 АПК РФ", "статья 2295", "229.5"),
        ("пункт 3 1 статьи 3 АПК РФ", "пункт 3 1 статьи 3", "3"),
        (" \r\nстатья\t\t450\r\nГК РФ  ", "статья\t\t450", "450"),
        ("префикс; статья 443[1] ГК РФ", "статья 443", "443"),
        ("статья 4\u00ad50 ГК РФ", "статья 4\u00ad50", "450"),
        ("статья 225.16\u20111 АПК РФ", "статья 225.16\u20111", "225.16-1"),
    ],
)
def test_repairs_anchor_to_the_actual_input_plane(source: str, raw: str, number: str) -> None:
    result = analyze(source, profile="ru")
    (occurrence,) = result.occurrences
    assert occurrence.raw == raw
    assert occurrence.references[0].article_number == number
    check_spans(source, result)
    assert result == analyze(source, profile="ru")
    assert asdict(result)["normalized_text"]


def test_coordinated_components_share_one_matched_source_span() -> None:
    text = "части 3, 4 статьи 65 АПК РФ; части 3, 4 статьи 65 АПК РФ"
    result = analyze(text, profile="ru")
    assert len(result.occurrences) == 2
    for occurrence in result.occurrences:
        assert occurrence.raw == "части 3, 4 статьи 65"
        assert [(r.article_number, r.part_number) for r in occurrence.references] == [
            ("65", "3"),
            ("65", "4"),
        ]
    assert len(extract_references(text, profile="ru")) == 2
    check_spans(text, result)


@pytest.mark.parametrize(
    "text,profile,family",
    [
        ("Article 100(1) GDPR; Article 100(1) GDPR", "eu", "gdpr"),
        ("15 U.S.C. § 78j; 15 U.S.C. § 78j", "us", "usc"),
        ("Article 5 VARA; Article 5 VARA", "ae", "vara"),
    ],
)
def test_existing_profile_rules_and_family_restrictions_are_shared(
    text: str, profile: str, family: str
) -> None:
    result = analyze(text, profile=profile, doc_family=family)
    check_spans(text, result)
    assert len(result.occurrences) >= 2
    assert all(
        r.doc_family == family for occurrence in result.occurrences for r in occurrence.references
    )
    legacy = extract_references(text, profile=profile, doc_family=family)
    assert set(legacy) == {r for occurrence in result.occurrences for r in occurrence.references}


def test_empty_no_match_and_conflicting_family_have_no_fabricated_occurrences() -> None:
    assert analyze(" \r\n ").occurrences == ()
    assert analyze("The clerk retained a copy.").occurrences == ()
    assert analyze("статья 10 НК РФ", profile="ru", doc_family="gk_rf").occurrences == ()
    with pytest.raises(ValueError, match="Unknown document family"):
        analyze("", profile="eu", doc_family="gk_rf")


def test_document_text_anchors_use_canonical_document_plane() -> None:
    from legal_chunking import chunk_text

    doc = chunk_text("Статья 1. Расходы\nСсылка: статья 225¹⁶⁻¹ АПК РФ.", profile="ru")
    result = analyze(doc.text, profile="ru")
    check_spans(doc.text, result)
    assert any(o.raw == "статья 225.16-1" for o in result.occurrences)


def test_deleted_prefix_artifact_does_not_shift_later_repeated_repairs() -> None:
    prefix = "Предисловие¹ " + "без ссылок " * 12 + "; "
    text = prefix + "статья 2295 АПК РФ; статья 229⁵ АПК РФ"
    result = analyze(text, profile="ru")
    assert "Предисловие¹" not in result.normalized_text
    first, second = result.occurrences
    assert first.start_offset == len(prefix)
    assert first.raw == "статья 2295"
    assert second.start_offset == text.index("статья 229⁵")
    assert second.raw == "статья 229⁵"
    assert first.references == second.references
    assert len(extract_references(text, profile="ru")) == 1
    check_spans(text, result)


def test_duplicate_list_members_are_preserved_inside_one_occurrence() -> None:
    text = "статьи 450, 450 ГК РФ"
    result = analyze(text, profile="ru")
    (occurrence,) = result.occurrences
    assert [r.article_number for r in occurrence.references] == ["450", "450"]
    assert len(extract_references(text, profile="ru")) == 1
    check_spans(text, result)


def test_occurrences_use_document_order_even_when_pattern_traversal_differs() -> None:
    text = "Section 1915; 28 U.S.C. § 1915; Section 1916; 28 U.S.C. § 1916"
    result = analyze(text, profile="us", doc_family="usc")
    check_spans(text, result)
    assert [o.start_offset for o in result.occurrences] == sorted(
        o.start_offset for o in result.occurrences
    )
    assert len(result.occurrences) == 4
    assert {r.article_number for o in result.occurrences for r in o.references} == {"1915", "1916"}


def test_compound_range_and_nested_reference_keep_matched_source_spellings() -> None:
    text = "статьи 225¹⁶⁻¹–225¹⁶⁻³ АПК РФ; пункт 3.2.1 статьи 450 ГК РФ"
    result = analyze(text, profile="ru")
    first, second = result.occurrences
    assert first.raw == "статьи 225¹⁶⁻¹–225¹⁶⁻³"
    assert first.references[0].article_number == "225.16-1–225.16-3"
    assert second.raw == "пункт 3.2.1 статьи 450"
    assert second.references[0].paragraph_number == "3.2.1"
    check_spans(text, result)


def test_manifest_alias_resolves_result_profile_without_extra_canonicalization() -> None:
    result = analyze("статья 450 ГК РФ", profile="russia")
    assert result.profile == "ru"
    assert result == analyze("статья 450 ГК РФ", profile="ru")
