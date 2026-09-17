import pytest

from legal_chunking import ParsedReference, extract_references
from legal_chunking.reference_context import ReferenceContextResolver
from legal_chunking.references import (
    normalize_article_number,
    normalize_legal_text,
    normalize_numeric_scripts,
    normalize_reference_text,
)


def test_normalize_numeric_scripts_converts_superscripts_and_subscripts() -> None:
    assert normalize_numeric_scripts("171² and 10₄") == "171.2 and 104"


def test_normalize_article_number_preserves_canonical_value() -> None:
    assert normalize_article_number(" 159¹ ") == "159.1"
    assert normalize_article_number("229_5") == "229.5"
    assert normalize_article_number("229(5)") == "229.5"
    assert normalize_article_number("229-5") == "229-5"


def test_normalize_legal_text_repairs_ru_split_decimal_reference() -> None:
    text = "пункт 3 1 статьи 3 АПК РФ"

    assert normalize_legal_text(text, profile="ru") == "пункт 3.1 статьи 3 АПК РФ"


def test_normalize_legal_text_repairs_ru_merged_article_decimal() -> None:
    text = "статья 2295 АПК РФ"

    assert normalize_legal_text(text, profile="ru") == "статья 229.5 АПК РФ"


def test_normalize_legal_text_normalizes_contextual_article_suffix_variants() -> None:
    assert normalize_legal_text("Статья 229⁵ ГПК РФ", profile="ru") == "Статья 229.5 ГПК РФ"
    assert normalize_legal_text("Статья 333² НК РФ", profile="ru") == "Статья 333.2 НК РФ"
    assert normalize_legal_text("Статья 229_5 ГПК РФ", profile="ru") == "Статья 229.5 ГПК РФ"
    assert normalize_legal_text("Статья 229(5) ГПК РФ", profile="ru") == "Статья 229.5 ГПК РФ"
    assert normalize_legal_text("Статья 229-5 ГПК РФ", profile="ru") == "Статья 229-5 ГПК РФ"


def test_normalize_legal_text_strips_explicit_bracket_footnote_only() -> None:
    text = "статья 443[1] ГК РФ"

    assert normalize_legal_text(text, profile="ru") == "статья 443 ГК РФ"
    assert normalize_legal_text("статья 5[1] ГК РФ", profile="ru") == "статья 5 ГК РФ"
    assert normalize_legal_text("статья 1000[1] ГК РФ", profile="ru") == "статья 1000 ГК РФ"


def test_normalize_legal_text_drops_non_reference_footnote_markers() -> None:
    assert normalize_legal_text("Условие договора¹", profile="ru") == "Условие договора"
    assert normalize_legal_text("Комментарий[12]", profile="ru") == "Комментарий"


def test_normalize_reference_text_collapses_whitespace_after_normalization() -> None:
    text = "  171²   ук   "

    assert normalize_reference_text(text, profile="ru") == "171.2 ук"


def test_parsed_reference_to_canonical_parts_normalizes_numeric_components() -> None:
    ref = ParsedReference(
        raw="пункт 3¹ статьи 171² ГК РФ",
        scheme="ru_article",
        article_number="171²",
        paragraph_number="3¹",
        part_number=None,
        doc_family="gk_rf",
    )

    assert ref.to_canonical_parts(jurisdiction="ru") == {
        "jurisdiction": "ru",
        "scheme": "ru_article",
        "article_number": "171.2",
        "doc_family": "gk_rf",
        "paragraph_number": "3.1",
    }


def test_parsed_reference_to_dict_exposes_structured_fields() -> None:
    ref = ParsedReference(
        raw="15 U.S.C. § 78j",
        scheme="section",
        article_number="78j",
        paragraph_number=None,
        part_number=None,
        doc_family="usc",
    )

    assert ref.to_dict() == {
        "raw": "15 U.S.C. § 78j",
        "scheme": "section",
        "article_number": "78j",
        "paragraph_number": None,
        "part_number": None,
        "doc_family": "usc",
    }


def test_parsed_reference_to_canonical_parts_preserves_full_paragraph_number() -> None:
    ref = ParsedReference(
        raw="пункт 3.2.1 статьи 450 ГК РФ",
        scheme="ru_article",
        article_number="450",
        paragraph_number="3.2.1",
        part_number=None,
        doc_family="gk_rf",
    )

    assert ref.to_canonical_parts(jurisdiction="ru") == {
        "jurisdiction": "ru",
        "scheme": "ru_article",
        "article_number": "450",
        "doc_family": "gk_rf",
        "paragraph_number": "3.2.1",
    }


def test_parsed_reference_to_canonical_parts_normalizes_jurisdiction_alias() -> None:
    ref = ParsedReference(
        raw="15 U.S.C. § 78j",
        scheme="section",
        article_number="78j",
        paragraph_number=None,
        part_number=None,
        doc_family="usc",
    )

    assert ref.to_canonical_parts(jurisdiction="U.S.") == {
        "jurisdiction": "us",
        "scheme": "section",
        "article_number": "78j",
        "doc_family": "usc",
    }


def test_parsed_reference_to_canonical_parts_rejects_missing_article_number() -> None:
    ref = ParsedReference(
        raw="Article",
        scheme="article",
        article_number=None,
        paragraph_number=None,
        part_number=None,
        doc_family=None,
    )

    try:
        ref.to_canonical_parts(jurisdiction="ru")
    except ValueError as exc:
        assert "article_number" in str(exc)
    else:
        raise AssertionError("Expected canonical parts to reject missing article_number")


def test_normalize_legal_text_preserves_plain_range_endpoints() -> None:
    text = "пункт 1-20 статьи 5 АПК РФ"

    assert normalize_legal_text(text, profile="ru") == "пункт 1-20 статьи 5 АПК РФ"


def test_normalize_legal_text_repairs_ru_range_end_only_for_decimal_like_case() -> None:
    text = "пунктов 1–61 статьи 101 НК РФ"

    assert normalize_legal_text(text, profile="ru") == "пунктов 1–6.1 статьи 101 НК РФ"


def test_normalize_legal_text_preserves_plain_three_digit_heading_prefix() -> None:
    text = "100 АПК РФ"

    assert normalize_legal_text(text, profile="ru") == "100 АПК РФ"


def test_normalize_legal_text_repairs_ru_heading_decimal_when_bounded() -> None:
    text = "291 АПК РФ"

    assert normalize_legal_text(text, profile="ru") == "29.1 АПК РФ"


def test_normalize_legal_text_preserves_unknown_numeric_suffix_without_context() -> None:
    assert normalize_legal_text("229⁵", profile="ru") == "229⁵"
    assert normalize_legal_text("229(5)", profile="ru") == "229(5)"
    assert normalize_legal_text("статьи 10-20 ГК РФ", profile="ru") == "статьи 10-20 ГК РФ"


def test_reference_context_resolver_uses_vocabulary_families() -> None:
    resolver = ReferenceContextResolver("ru")

    assert resolver.detect_context("Статья 229⁵ ГПК РФ").family == "article_like"
    assert resolver.detect_context("часть 2 статьи 2881 АПК РФ").family == "article_like"
    assert resolver.detect_context("разд 3 ГК РФ").family == "section_like"
    assert resolver.detect_context("Условие договора¹").family == "unknown"


def test_normalize_legal_text_preserves_zero_ending_chapter_numbers() -> None:
    text = "глава 100 АПК РФ"

    assert normalize_legal_text(text, profile="ru") == "глава 100 АПК РФ"


def test_extract_references_parses_ru_article_context() -> None:
    refs = extract_references("пункт 3 статьи 450 ГК РФ", profile="ru")

    assert len(refs) == 1
    assert refs[0].scheme == "ru_article"
    assert refs[0].article_number == "450"
    assert refs[0].paragraph_number == "3"
    assert refs[0].doc_family == "gk_rf"


def test_extract_references_parses_usc_section_with_doc_family_narrowing() -> None:
    refs = extract_references("15 U.S.C. § 78j", profile="us", doc_family="usc")

    assert len(refs) == 1
    assert refs[0].scheme == "section"
    assert refs[0].article_number == "78j"
    assert refs[0].doc_family == "usc"


def test_extract_references_us_doc_family_narrowing_excludes_other_family_matches() -> None:
    refs = extract_references(
        "15 U.S.C. § 78j and 17 C.F.R. § 240.10b-5",
        profile="us",
        doc_family="usc",
    )

    assert [(ref.article_number, ref.doc_family) for ref in refs] == [("78j", "usc")]


def test_extract_references_resolves_doc_family_per_match() -> None:
    refs = extract_references(
        "15 U.S.C. § 78j and 17 C.F.R. § 240.10b-5",
        profile="us",
    )

    assert [(ref.article_number, ref.doc_family) for ref in refs] == [
        ("78j", "usc"),
        ("240.10b-5", "cfr"),
    ]


def test_extract_references_uses_nearest_doc_family_alias_for_generic_ru_matches() -> None:
    refs = extract_references(
        "ст.5 ГК РФ и ст.10 НК РФ",
        profile="ru",
    )

    assert [(ref.article_number, ref.doc_family) for ref in refs] == [
        ("5", "gk_rf"),
        ("10", "nk_rf"),
    ]


def test_extract_references_parses_compact_ru_marker_number_form() -> None:
    refs = extract_references("ст.5 ГК РФ", profile="ru")

    assert [(ref.scheme, ref.article_number, ref.doc_family) for ref in refs] == [
        ("ru_article", "5", "gk_rf"),
    ]


def test_extract_references_skips_eu_matches_without_doc_family_when_required() -> None:
    refs = extract_references("Recital 10 applies here.", profile="eu")

    assert refs == []


def test_extract_references_parses_eu_match_with_doc_family_context() -> None:
    refs = extract_references("Recital 10 GDPR applies here.", profile="eu")

    assert [(ref.scheme, ref.article_number, ref.doc_family) for ref in refs] == [
        ("recital", "10", "gdpr"),
    ]


def test_extract_references_parses_ae_article_with_doc_family_context() -> None:
    refs = extract_references(
        "Article 5 VARA applies here.",
        profile="ae",
    )

    assert [(ref.scheme, ref.article_number, ref.doc_family) for ref in refs] == [
        ("article", "5", "vara"),
    ]


def test_extract_references_rejects_compact_ru_marker_inside_unrelated_word() -> None:
    refs = extract_references("ГОСТ.5 ГК РФ", profile="ru")

    assert refs == []


def test_extract_references_parses_compact_eu_marker_number_form() -> None:
    refs = extract_references("art.5 GDPR", profile="eu")

    assert [(ref.scheme, ref.article_number, ref.doc_family) for ref in refs] == [
        ("article", "5", "gdpr"),
    ]


def test_extract_references_parses_compact_us_marker_number_form() -> None:
    refs = extract_references("sec.5 CFR", profile="us")

    assert [(ref.scheme, ref.article_number, ref.doc_family) for ref in refs] == [
        ("section", "5", "cfr"),
    ]


def test_extract_references_parses_eu_recital() -> None:
    refs = extract_references("Recital (12) GDPR", profile="eu")

    assert len(refs) == 1
    assert refs[0].scheme == "recital"
    assert refs[0].article_number == "12"
    assert refs[0].doc_family == "gdpr"


def test_coordinated_ru_references_keep_their_article_container() -> None:
    refs = extract_references("части 3, 4 статьи 65 АПК РФ", profile="ru")
    assert [(r.scheme, r.article_number, r.part_number, r.doc_family) for r in refs] == [
        ("ru_article", "65", "3", "apk_rf"),
        ("ru_article", "65", "4", "apk_rf"),
    ]
    refs = extract_references("пункты 1, 2 части 3 статьи 10 ГК РФ", profile="ru")
    assert [(r.article_number, r.part_number, r.paragraph_number) for r in refs] == [
        ("10", "3", "1"),
        ("10", "3", "2"),
    ]
    assert all(r.raw == "пункты 1, 2 части 3 статьи 10" for r in refs)
    refs = extract_references("статьи 66, 72 ГК РФ", profile="ru")
    assert [r.article_number for r in refs] == ["66", "72"]


def test_extracted_reference_keeps_full_nested_number() -> None:
    refs = extract_references("пункт 3.2.1 статьи 450 ГК РФ", profile="ru")
    assert len(refs) == 1
    assert refs[0].paragraph_number == "3.2.1"


def test_chapter_references_are_not_articles_and_keep_list_order() -> None:
    refs = extract_references("главы 17, 29¹ АПК РФ", profile="ru")
    assert [(r.scheme, r.article_number) for r in refs] == [("chapter", "17"), ("chapter", "29.1")]


def test_numeric_repair_preserves_unapproved_numbers_and_ordinary_scripts() -> None:
    assert normalize_legal_text("глава 325 АПК РФ", profile="ru") == "глава 325 АПК РФ"
    assert normalize_legal_text("статья 1234 ГК РФ", profile="ru") == "статья 1234 ГК РФ"
    assert normalize_legal_text("статья 5; формула 100²", profile="ru") == "статья 5; формула 100²"
    assert normalize_legal_text("Article 100(1) GDPR", profile="eu") == "Article 100(1) GDPR"
    refs = extract_references("Article 100(1) GDPR", profile="eu")
    assert refs[0].article_number == "100(1)"
    assert refs[0].to_canonical_parts(jurisdiction="eu")["article_number"] == "100(1)"


def test_superscript_range_normalization_is_idempotent() -> None:
    assert normalize_article_number("171²-³") == "171.2-3"
    assert normalize_article_number("61.¹¹") == "61.11"
    text = normalize_legal_text("Статья 171²-³ УК РФ", profile="ru")
    assert text == "Статья 171.2-3 УК РФ"
    assert normalize_legal_text(text, profile="ru") == text


def test_reference_ranges_remain_ranges_without_invented_expansion() -> None:
    refs = extract_references("части 3–4 статьи 65 АПК РФ", profile="ru")
    assert [(r.article_number, r.part_number) for r in refs] == [("65", "3–4")]
    refs = extract_references("статьи 10–20, 443 ГК РФ", profile="ru")
    assert [r.article_number for r in refs] == ["10–20", "443"]


def test_explicit_document_family_cannot_override_jurisdiction() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unknown document family"):
        extract_references("Article 5 GDPR", profile="eu", doc_family="gk_rf")
    assert extract_references("статья 10 НК РФ", profile="ru", doc_family="gk_rf") == []
    refs = extract_references("15 U.S.C. § 78j", profile="us", doc_family=" USC ")
    assert refs[0].doc_family == "usc"


@pytest.mark.parametrize("number", ["225¹⁶⁻¹", "225¹⁶-¹", "225¹⁶-1", "225.16-1"])
def test_compound_article_suffix_is_consistent_across_structure_and_references(number: str) -> None:
    from legal_chunking import chunk_text

    normalized = "225.16-1"
    citation = f"статья {number} АПК РФ"
    assert normalize_article_number(number) == normalized
    assert normalize_legal_text(citation, profile="ru") == f"статья {normalized} АПК РФ"
    assert (
        normalize_legal_text(normalize_legal_text(citation, profile="ru"), profile="ru")
        == f"статья {normalized} АПК РФ"
    )
    doc = chunk_text(f"Статья {number}. Расходы\nТекст статьи.", profile="ru")
    assert doc.sections[1].metadata.article_number == normalized
    assert doc.chunks[0].metadata.article_number == normalized
    refs = extract_references(citation, profile="ru")
    assert [(r.article_number, r.doc_family) for r in refs] == [(normalized, "apk_rf")]
    assert refs[0].to_canonical_parts(jurisdiction="ru")["article_number"] == normalized
    assert (
        refs[0].article_number
        == extract_references(doc.text, profile="ru", doc_family="apk_rf")[0].article_number
    )


@pytest.mark.parametrize(
    "citation,numbers",
    [
        ("статьи 10–20 АПК РФ", ["10–20"]),
        ("статьи 10-20 АПК РФ", ["10-20"]),
        ("статья 229-5 АПК РФ", ["229-5"]),
        ("статьи 225.16-1, 225.16-3 АПК РФ", ["225.16-1", "225.16-3"]),
        ("статьи 225.16-1–225.16-3 АПК РФ", ["225.16-1–225.16-3"]),
        ("часть 2 статьи 225.16-1 АПК РФ", ["225.16-1"]),
    ],
)
def test_compound_article_and_range_spelling_is_preserved(
    citation: str, numbers: list[str]
) -> None:
    assert normalize_legal_text(citation, profile="ru") == citation
    refs = extract_references(citation, profile="ru")
    assert [r.article_number for r in refs] == numbers
    assert [r.to_canonical_parts(jurisdiction="ru")["article_number"] for r in refs] == numbers
    if citation.startswith("часть"):
        assert refs[0].part_number == "2"
