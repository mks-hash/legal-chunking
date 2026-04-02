"""Jurisdiction- and doc-family-aware legal reference parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from legal_chunking.numbering_markers import (
    build_numbering_marker_pattern,
    get_numbering_family_aliases,
)
from legal_chunking.profiles import resolve_doc_family, resolve_profile
from legal_chunking.references import normalize_article_number, normalize_legal_query_text


@dataclass(slots=True, frozen=True)
class ParsedReference:
    raw: str
    scheme: str
    article_number: str | None
    paragraph_number: str | None
    part_number: str | None
    doc_family: str | None = None


_ARTICLE_TOKEN = r"(?:[A-Za-z]\.?\s*)?\d+[A-Za-z0-9()./-]*"


def _build_asset_marker_patterns(
    *,
    profile: str,
    family: str,
    scheme: str,
) -> list[tuple[str, re.Pattern[str]]]:
    aliases = [
        alias
        for alias in get_numbering_family_aliases(profile=profile, family=family)
        if any(char.isalpha() for char in alias)
    ]
    if not aliases:
        return []
    marker = "(?:" + "|".join(
        sorted((re.escape(alias) for alias in aliases), key=len, reverse=True)
    ) + ")"
    return [
        (
            scheme,
            re.compile(rf"(?<!\w)(?:{marker})\s+(?P<article>{_ARTICLE_TOKEN})", re.IGNORECASE),
        )
    ]


def _ru_scoped_patterns(profile: str) -> list[re.Pattern[str]]:
    article_marker = build_numbering_marker_pattern(profile=profile, family="article_like")
    point_marker = build_numbering_marker_pattern(profile=profile, family="point_like")
    part_marker = build_numbering_marker_pattern(profile=profile, family="part_like")
    return [
        re.compile(
            rf"(?:(?P<part>{part_marker}\s*\d+)\s*)?"
            rf"(?:(?P<paragraph>{point_marker}\s*\d+(?:\.\d+)*)\s*)?"
            rf"(?:{article_marker})\s+(?P<article>\d+(?:\.\d+)*)",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?:(?P<paragraph>{point_marker}\s*\d+(?:\.\d+)*)\s*)?"
            rf"(?:(?P<part>{part_marker}\s*\d+)\s*)?"
            rf"(?:{article_marker})\s+(?P<article>\d+(?:\.\d+)*)",
            re.IGNORECASE,
        ),
    ]


_GERMAN_SECTION_PATTERNS = [
    re.compile(
        rf"§\s*(?P<article>{_ARTICLE_TOKEN})\s*(?:(?P<paragraph>Abs\.?\s*\d+)\s*)?(?:(?P<part>Satz\s*\d+)\s*)?",
        re.IGNORECASE,
    ),
]
_COMMON_SECTION_ABBREV_PATTERNS = [
    ("section", re.compile(rf"\bs\.?\s+(?P<article>{_ARTICLE_TOKEN})", re.IGNORECASE)),
]
_US_SECTION_SIGN_PATTERNS = [
    (
        "section",
        re.compile(
            rf"\b\d+\s+U\.?\s*S\.?\s*C\.?\s*§+\s*(?P<article>{_ARTICLE_TOKEN})",
            re.IGNORECASE,
        ),
    ),
    (
        "section",
        re.compile(
            rf"\b\d+\s+C\.?\s*F\.?\s*R\.?\s*§+\s*(?P<article>{_ARTICLE_TOKEN})",
            re.IGNORECASE,
        ),
    ),
]
_DOC_FAMILY_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "usc": [
        (
            "section",
            re.compile(
                rf"\b\d+\s+U\.?\s*S\.?\s*C\.?\s*§+\s*(?P<article>{_ARTICLE_TOKEN})",
                re.IGNORECASE,
            ),
        ),
    ],
    "cfr": [
        (
            "section",
            re.compile(
                rf"\b\d+\s+C\.?\s*F\.?\s*R\.?\s*§+\s*(?P<article>{_ARTICLE_TOKEN})",
                re.IGNORECASE,
            ),
        ),
    ],
}


def _asset_generic_patterns_for_profile(profile: str) -> list[tuple[str, re.Pattern[str]]]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    patterns.extend(
        _build_asset_marker_patterns(
            profile=profile,
            family="article_like",
            scheme="article",
        )
    )
    patterns.extend(
        _build_asset_marker_patterns(
            profile=profile,
            family="section_like",
            scheme="section",
        )
    )
    return patterns


def _jurisdiction_scheme_patterns(
    profile: str,
    *,
    doc_family: str | None = None,
) -> tuple[list[re.Pattern[str]], list[tuple[str, re.Pattern[str]]]]:
    code = resolve_profile(profile).code
    family = (doc_family or "").strip().lower()
    scoped_patterns: list[re.Pattern[str]] = []
    generic_patterns: list[tuple[str, re.Pattern[str]]] = []

    if code == "ru":
        scoped_patterns = _ru_scoped_patterns(code)
    elif code in {"de", "ch"}:
        scoped_patterns = list(_GERMAN_SECTION_PATTERNS)
        generic_patterns.extend(
            _build_asset_marker_patterns(
                profile="eu",
                family="section_like",
                scheme="section",
            )
        )
    elif code == "us":
        generic_patterns.extend(_asset_generic_patterns_for_profile(code))
        generic_patterns.extend(_US_SECTION_SIGN_PATTERNS)
    elif code == "eu":
        generic_patterns.extend(_asset_generic_patterns_for_profile(code))
        generic_patterns.extend(
            [
                (
                    "recital",
                    re.compile(rf"\bRecital\s+(?P<article>{_ARTICLE_TOKEN})", re.IGNORECASE),
                ),
                (
                    "recital",
                    re.compile(
                        rf"\bRecital\s*\((?P<article>{_ARTICLE_TOKEN})\)",
                        re.IGNORECASE,
                    ),
                ),
            ]
        )
    else:
        generic_patterns.extend(_asset_generic_patterns_for_profile("generic"))
        generic_patterns.extend(_COMMON_SECTION_ABBREV_PATTERNS)

    if family in _DOC_FAMILY_PATTERNS:
        generic_patterns = [*_DOC_FAMILY_PATTERNS[family], *generic_patterns]
    return scoped_patterns, generic_patterns


def _extract_number(raw: str | None) -> str | None:
    if not raw:
        return None
    normalized = normalize_article_number(raw)
    if not normalized:
        return None
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    return match.group(0) if match else None


def extract_references(
    text: str,
    *,
    profile: str = "generic",
    doc_family: str | None = None,
) -> list[ParsedReference]:
    resolved_profile = resolve_profile(profile)
    family = doc_family or (resolve_doc_family(resolved_profile.code, text or "") or None)
    family_id = family.id if hasattr(family, "id") else family
    text_norm = normalize_legal_query_text(text or "", profile=resolved_profile.code)
    results: list[ParsedReference] = []
    seen: set[tuple[str, str | None, str | None, str | None, str | None]] = set()
    scoped_patterns, generic_patterns = _jurisdiction_scheme_patterns(
        resolved_profile.code,
        doc_family=family_id,
    )

    def append_reference(ref: ParsedReference) -> None:
        key = (
            ref.scheme,
            ref.article_number,
            ref.paragraph_number,
            ref.part_number,
            ref.doc_family,
        )
        if key in seen:
            return
        seen.add(key)
        results.append(ref)

    for pattern in scoped_patterns:
        for match in pattern.finditer(text_norm):
            article = normalize_article_number(match.groupdict().get("article"))
            if not article:
                continue
            append_reference(
                ParsedReference(
                    raw=match.group(0),
                    scheme="ru_article" if resolved_profile.code == "ru" else "section",
                    article_number=str(article),
                    paragraph_number=_extract_number(match.groupdict().get("paragraph")),
                    part_number=_extract_number(match.groupdict().get("part")),
                    doc_family=family_id,
                )
            )

    for scheme, pattern in generic_patterns:
        for match in pattern.finditer(text_norm):
            article = normalize_article_number(match.group("article"))
            if not article:
                continue
            append_reference(
                ParsedReference(
                    raw=match.group(0),
                    scheme=scheme,
                    article_number=str(article),
                    paragraph_number=None,
                    part_number=None,
                    doc_family=family_id,
                )
            )

    return results


def normalize_reference(
    ref: ParsedReference,
    *,
    profile: str,
    doc_family: str | None = None,
) -> str | None:
    if not ref.article_number:
        return None
    family = doc_family or ref.doc_family or "unknown"
    parts = [
        f"jur={resolve_profile(profile).code}",
        f"doc={family}",
        f"scheme={(ref.scheme or 'article').lower()}",
        f"article={normalize_article_number(ref.article_number) or ref.article_number}",
    ]
    if ref.paragraph_number:
        parts.append(f"paragraph={ref.paragraph_number}")
    if ref.part_number:
        parts.append(f"part={ref.part_number}")
    return "|".join(parts)


__all__ = ["ParsedReference", "extract_references", "normalize_reference"]
