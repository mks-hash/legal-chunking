from legal_chunking import (
    ReferenceContextResolver,
    normalize_article_number,
    normalize_legal_query_text,
    normalize_legal_text,
    normalize_normalized_ref,
    normalize_normalized_refs,
    normalize_numeric_scripts,
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


def test_reference_context_resolver_uses_vocabulary_families() -> None:
    resolver = ReferenceContextResolver("ru")

    assert resolver.detect_context("Статья 229⁵ ГПК РФ").family == "article_like"
    assert resolver.detect_context("часть 2 статьи 2881 АПК РФ").family == "article_like"
    assert resolver.detect_context("Условие договора¹").family == "unknown"
