from legal_chunking import (
    ReferenceContextResolver,
    extract_references,
    normalize_article_number,
    normalize_legal_query_text,
    normalize_legal_text,
    normalize_normalized_ref,
    normalize_normalized_refs,
    normalize_numeric_scripts,
    normalize_reference,
)


def test_normalize_numeric_scripts_converts_superscripts_and_subscripts() -> None:
    assert normalize_numeric_scripts("171² and 10₄") == "171.2 and 104"


def test_normalize_article_number_preserves_canonical_value() -> None:
    assert normalize_article_number(" 159¹ ") == "159.1"
    assert normalize_article_number("229_5") == "229.5"
    assert normalize_article_number("229(5)") == "229.5"
    assert normalize_article_number("229-5") == "229.5"


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
    assert normalize_legal_text("Статья 229-5 ГПК РФ", profile="ru") == "Статья 229.5 ГПК РФ"


def test_normalize_legal_text_strips_explicit_bracket_footnote_only() -> None:
    text = "статья 443[1] ГК РФ"

    assert normalize_legal_text(text, profile="ru") == "статья 443 ГК РФ"
    assert normalize_legal_text("статья 5[1] ГК РФ", profile="ru") == "статья 5 ГК РФ"
    assert normalize_legal_text("статья 1000[1] ГК РФ", profile="ru") == "статья 1000 ГК РФ"


def test_normalize_legal_text_drops_non_reference_footnote_markers() -> None:
    assert normalize_legal_text("Условие договора¹", profile="ru") == "Условие договора"
    assert normalize_legal_text("Комментарий[12]", profile="ru") == "Комментарий"


def test_normalize_legal_query_text_collapses_whitespace_after_normalization() -> None:
    text = "  171²   ук   "

    assert normalize_legal_query_text(text, profile="ru") == "171.2 ук"


def test_normalize_normalized_ref_normalizes_numeric_components() -> None:
    ref = "article=171²|paragraph=3¹|scheme=ru_article"

    assert normalize_normalized_ref(ref) == "article=171.2|paragraph=3.1|scheme=ru_article"


def test_normalize_normalized_refs_deduplicates_stably() -> None:
    refs = [
        "article=171²|scheme=ru_article",
        "article=171.2|scheme=ru_article",
        "article=302|scheme=ru_article",
    ]

    assert normalize_normalized_refs(refs) == [
        "article=171.2|scheme=ru_article",
        "article=302|scheme=ru_article",
    ]


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


def test_extract_references_parses_eu_recital() -> None:
    refs = extract_references("Recital (12) GDPR", profile="eu")

    assert len(refs) == 1
    assert refs[0].scheme == "recital"
    assert refs[0].article_number == "12"
    assert refs[0].doc_family == "gdpr"


def test_normalize_reference_builds_canonical_reference_string() -> None:
    ref = extract_references("пункт 3 статьи 450 ГК РФ", profile="ru")[0]

    assert normalize_reference(ref, profile="ru") == (
        "jur=ru|doc=gk_rf|scheme=ru_article|article=450|paragraph=3"
    )
