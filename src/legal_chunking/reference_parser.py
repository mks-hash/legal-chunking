"""Jurisdiction- and doc-family-aware legal reference parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from legal_chunking.manifest import ReferenceDocFamily
from legal_chunking.numbering_markers import (
    build_numbering_marker_pattern,
    get_numbering_family_aliases,
)
from legal_chunking.profiles import resolve_doc_family, resolve_profile
from legal_chunking.references import normalize_article_number, normalize_reference_text


@dataclass(slots=True, frozen=True)
class ParsedReference:
    raw: str
    scheme: str
    article_number: str | None
    paragraph_number: str | None
    part_number: str | None
    doc_family: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "raw": self.raw,
            "scheme": self.scheme,
            "article_number": self.article_number,
            "paragraph_number": self.paragraph_number,
            "part_number": self.part_number,
            "doc_family": self.doc_family,
        }

    def to_canonical_parts(self, *, jurisdiction: str) -> dict[str, str]:
        normalized_jurisdiction = resolve_profile(jurisdiction).code
        article_number = normalize_article_number(self.article_number)
        if not article_number:
            raise ValueError("ParsedReference must contain article_number for canonical parts")
        parts = {
            "jurisdiction": normalized_jurisdiction,
            "scheme": (self.scheme or "article").lower(),
            "article_number": article_number,
        }
        if self.doc_family:
            parts["doc_family"] = self.doc_family
        if self.paragraph_number:
            parts["paragraph_number"] = (
                normalize_article_number(self.paragraph_number) or self.paragraph_number
            )
        if self.part_number:
            parts["part_number"] = normalize_article_number(self.part_number) or self.part_number
        return parts


_ARTICLE_TOKEN = r"(?:[A-Za-z]\.?\s*)?\d+[A-Za-z0-9()./-]*"
_FAMILY_CONTEXT_CHARS = 96


@dataclass(slots=True, frozen=True)
class _PatternSpec:
    scheme: str
    pattern: re.Pattern[str]
    doc_family: str | None = None


def _build_asset_marker_patterns(
    *,
    profile: str,
    family: str,
    scheme: str,
) -> list[_PatternSpec]:
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
        _PatternSpec(
            scheme=scheme,
            pattern=re.compile(
                rf"(?<!\w)(?:{marker})\s+(?P<article>{_ARTICLE_TOKEN})",
                re.IGNORECASE,
            ),
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
    _PatternSpec(
        scheme="section",
        pattern=re.compile(rf"\bs\.?\s+(?P<article>{_ARTICLE_TOKEN})", re.IGNORECASE),
    ),
]
_US_SECTION_SIGN_PATTERNS = [
    _PatternSpec(
        scheme="section",
        pattern=re.compile(
            rf"\b\d+\s+U\.?\s*S\.?\s*C\.?\s*§+\s*(?P<article>{_ARTICLE_TOKEN})",
            re.IGNORECASE,
        ),
        doc_family="usc",
    ),
    _PatternSpec(
        scheme="section",
        pattern=re.compile(
            rf"\b\d+\s+C\.?\s*F\.?\s*R\.?\s*§+\s*(?P<article>{_ARTICLE_TOKEN})",
            re.IGNORECASE,
        ),
        doc_family="cfr",
    ),
]
_DOC_FAMILY_PATTERNS: dict[str, list[_PatternSpec]] = {
    "usc": [
        _PatternSpec(
            scheme="section",
            pattern=re.compile(
                rf"\b\d+\s+U\.?\s*S\.?\s*C\.?\s*§+\s*(?P<article>{_ARTICLE_TOKEN})",
                re.IGNORECASE,
            ),
            doc_family="usc",
        ),
    ],
    "cfr": [
        _PatternSpec(
            scheme="section",
            pattern=re.compile(
                rf"\b\d+\s+C\.?\s*F\.?\s*R\.?\s*§+\s*(?P<article>{_ARTICLE_TOKEN})",
                re.IGNORECASE,
            ),
            doc_family="cfr",
        ),
    ],
}


def _asset_generic_patterns_for_profile(profile: str) -> list[_PatternSpec]:
    patterns: list[_PatternSpec] = []
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
) -> tuple[list[re.Pattern[str]], list[_PatternSpec]]:
    code = resolve_profile(profile).code
    family = (doc_family or "").strip().lower()
    scoped_patterns: list[re.Pattern[str]] = []
    generic_patterns: list[_PatternSpec] = []

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
        if family in _DOC_FAMILY_PATTERNS:
            generic_patterns.extend(_DOC_FAMILY_PATTERNS[family])
        else:
            generic_patterns.extend(_US_SECTION_SIGN_PATTERNS)
    elif code == "eu":
        generic_patterns.extend(_asset_generic_patterns_for_profile(code))
        generic_patterns.extend(
            [
                _PatternSpec(
                    scheme="recital",
                    pattern=re.compile(
                        rf"\bRecital\s+(?P<article>{_ARTICLE_TOKEN})",
                        re.IGNORECASE,
                    ),
                ),
                _PatternSpec(
                    scheme="recital",
                    pattern=re.compile(
                        rf"\bRecital\s*\((?P<article>{_ARTICLE_TOKEN})\)",
                        re.IGNORECASE,
                    ),
                ),
            ]
        )
    else:
        generic_patterns.extend(_asset_generic_patterns_for_profile("generic"))
        generic_patterns.extend(_COMMON_SECTION_ABBREV_PATTERNS)

    if code != "us" and family in _DOC_FAMILY_PATTERNS:
        generic_patterns = [*_DOC_FAMILY_PATTERNS[family], *generic_patterns]
    return scoped_patterns, generic_patterns


def _resolve_match_doc_family(
    *,
    text: str,
    match: re.Match[str],
    profile: str,
    explicit_doc_family: str | None,
    inherited_doc_family: str | ReferenceDocFamily | None,
) -> str | None:
    if explicit_doc_family:
        return explicit_doc_family

    context_start = max(0, match.start() - _FAMILY_CONTEXT_CHARS)
    context_end = min(len(text), match.end() + _FAMILY_CONTEXT_CHARS)
    context = text[context_start:context_end]
    family = resolve_doc_family(profile, context)
    if family is not None:
        return family.id

    if isinstance(inherited_doc_family, ReferenceDocFamily):
        return inherited_doc_family.id
    return inherited_doc_family


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
    inherited_family = doc_family or (
        resolve_doc_family(resolved_profile.code, text or "") or None
    )
    inherited_family_id = (
        inherited_family.id
        if isinstance(inherited_family, ReferenceDocFamily)
        else inherited_family
    )
    text_norm = normalize_reference_text(text or "", profile=resolved_profile.code)
    results: list[ParsedReference] = []
    seen: set[tuple[str, str | None, str | None, str | None, str | None]] = set()
    scoped_patterns, generic_patterns = _jurisdiction_scheme_patterns(
        resolved_profile.code,
        doc_family=doc_family,
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
            match_family = _resolve_match_doc_family(
                text=text_norm,
                match=match,
                profile=resolved_profile.code,
                explicit_doc_family=inherited_family_id,
                inherited_doc_family=inherited_family,
            )
            append_reference(
                ParsedReference(
                    raw=match.group(0),
                    scheme="ru_article" if resolved_profile.code == "ru" else "section",
                    article_number=str(article),
                    paragraph_number=_extract_number(match.groupdict().get("paragraph")),
                    part_number=_extract_number(match.groupdict().get("part")),
                    doc_family=match_family,
                )
            )

    for spec in generic_patterns:
        for match in spec.pattern.finditer(text_norm):
            article = normalize_article_number(match.group("article"))
            if not article:
                continue
            match_family = _resolve_match_doc_family(
                text=text_norm,
                match=match,
                profile=resolved_profile.code,
                explicit_doc_family=spec.doc_family or inherited_family_id,
                inherited_doc_family=inherited_family,
            )
            append_reference(
                ParsedReference(
                    raw=match.group(0),
                    scheme=spec.scheme,
                    article_number=str(article),
                    paragraph_number=None,
                    part_number=None,
                    doc_family=match_family,
                )
            )

    return results
__all__ = ["ParsedReference", "extract_references"]
