from legal_chunking import chunk_pdf, chunk_text
from legal_chunking.manifest import load_manifest
from legal_chunking.numbering_markers import (
    build_numbering_marker_pattern,
    get_numbering_aliases,
    get_numbering_family_aliases,
)
from legal_chunking.profiles import resolve_doc_family, resolve_profile


def test_load_manifest_exposes_enabled_profiles() -> None:
    manifest = load_manifest()

    assert manifest.version == 1
    assert manifest.enabled_profiles() == {"generic", "ru", "us", "eu"}


def test_resolve_profile_by_alias_returns_canonical_code() -> None:
    profile = resolve_profile("russia")

    assert profile.code == "ru"
    assert profile.language == "ru"
    assert profile.doc_families
    assert profile.heading_patterns["version"] == 1
    assert profile.numbering_markers["version"] == 1
    assert profile.chunking_policy["version"] == 1


def test_chunk_text_uses_resolved_profile_metadata() -> None:
    document = chunk_text("Article 1. Test clause", profile="u.s.")

    assert document.profile == "us"
    assert document.language == "en"


def test_chunk_pdf_uses_resolved_profile_metadata() -> None:
    document = chunk_pdf("agreement.pdf", profile="european union")

    assert document.profile == "eu"
    assert document.language == "en"


def test_unknown_profile_raises_value_error() -> None:
    try:
        resolve_profile("unknown-profile")
    except ValueError as exc:
        assert "Unknown or disabled profile" in str(exc)
    else:
        raise AssertionError("Expected resolve_profile to reject an unknown profile")


def test_unknown_doc_kind_uses_other_policy_before_code_default() -> None:
    document = chunk_text("Internal note body.", profile="generic", doc_kind="internal_memo")

    assert document.chunk_policy == "default"


def test_guidance_doc_kind_resolves_to_guidance_policy() -> None:
    document = chunk_text("Guidance body.", profile="generic", doc_kind="guidance")

    assert document.chunk_policy == "guidance"


def test_numbering_family_aliases_are_asset_backed() -> None:
    aliases = get_numbering_family_aliases(profile="ru", family="article_like")

    assert "статья" in aliases
    assert "ст." in aliases


def test_numbering_aliases_deduplicate_across_families() -> None:
    aliases = get_numbering_aliases(
        profile="us",
        families=["section_like", "paragraph_like", "section_like"],
    )

    assert aliases.count("section") == 1
    assert "§" in aliases


def test_build_numbering_marker_pattern_prefers_longer_aliases_first() -> None:
    pattern = build_numbering_marker_pattern(profile="us", family="section_like")
    parts = pattern.removeprefix("(?:").removesuffix(")").split("|")

    assert pattern.startswith("(?:")
    assert parts[:2] == ["sections", "section"]


def test_resolve_doc_family_by_manifest_alias() -> None:
    family = resolve_doc_family("ru", "Статья 229.5 ГПК РФ")

    assert family is not None
    assert family.id == "gpk_rf"


def test_resolve_doc_family_supports_expanded_ru_manifest_aliases() -> None:
    family = resolve_doc_family("ru", "Постановление Пленума Верховного Суда РФ № 25")

    assert family is not None
    assert family.id == "vs_plenum"


def test_resolve_doc_family_supports_expanded_us_manifest_aliases() -> None:
    family = resolve_doc_family("us", "See also U.S. Bankruptcy Code section 362")

    assert family is not None
    assert family.id == "bankruptcy_code"


def test_resolve_doc_family_supports_expanded_eu_manifest_aliases() -> None:
    family = resolve_doc_family("eu", "CJEU judgment in Case C-311/18")

    assert family is not None
    assert family.id == "cjeu"
