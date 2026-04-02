from legal_chunking import chunk_pdf, chunk_text, load_manifest, resolve_profile


def test_load_manifest_exposes_enabled_profiles() -> None:
    manifest = load_manifest()

    assert manifest.version == 1
    assert manifest.enabled_profiles() == {"generic", "ru", "us", "eu"}


def test_resolve_profile_by_alias_returns_canonical_code() -> None:
    profile = resolve_profile("russia")

    assert profile.code == "ru"
    assert profile.language == "ru"
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
