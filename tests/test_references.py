from legal_chunking import (
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


def test_normalize_legal_text_repairs_ru_split_decimal_reference() -> None:
    text = "пункт 3 1 статьи 3 АПК РФ"

    assert normalize_legal_text(text, profile="ru") == "пункт 3.1 статьи 3 АПК РФ"


def test_normalize_legal_text_repairs_ru_merged_article_decimal() -> None:
    text = "статья 2295 АПК РФ"

    assert normalize_legal_text(text, profile="ru") == "статья 229.5 АПК РФ"


def test_normalize_legal_text_strips_explicit_bracket_footnote_only() -> None:
    text = "статья 443[1] ГК РФ"

    assert normalize_legal_text(text, profile="ru") == "статья 443 ГК РФ"


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
