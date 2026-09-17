"""Deterministic legal reference normalization helpers."""

from __future__ import annotations

import re
from functools import lru_cache

from legal_chunking.legal_normalization import (
    _normalize_structural_numbering_view,
    approved_number,
    normalize_number_scripts,
    numeric_script_rules,
    repair_patterns,
)
from legal_chunking.normalize import _normalize_extracted_view
from legal_chunking.numbering_markers import get_numbering_aliases
from legal_chunking.profiles import resolve_profile
from legal_chunking.reference_context import ReferenceContextResolver
from legal_chunking.text_mapping import _TextView

_SCRIPT_SUFFIX_PATTERN, _SUPERSCRIPT_TRANS, _SUBSCRIPT_TRANS = numeric_script_rules()
_SUPERSCRIPT_SUFFIX_RE = re.compile(
    r"(?P<base>\d{1,4})(?P<suffix>" + _SCRIPT_SUFFIX_PATTERN.pattern + r")"
)
_STRUCTURED_SUFFIX_RE = re.compile(
    r"(?P<base>\d{2,4})(?:\((?P<paren>\d{1,2})\)|_(?P<underscore>\d{1,2}))"
)
_WORD_SUPERSCRIPT_FOOTNOTE_RE = re.compile(
    r"(?P<word>[A-Za-zА-Яа-яЁё]+)(?P<footnote>" + _SCRIPT_SUFFIX_PATTERN.pattern + r")"
)
_WORD_BRACKET_FOOTNOTE_RE = re.compile(r"(?P<word>[A-Za-zА-Яа-яЁё]+)\[(?P<footnote>\d+)\]")


def normalize_numeric_scripts(text: str) -> str:
    return normalize_number_scripts(text)


def normalize_article_number(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_numeric_scripts(value).strip()
    structured_match = _STRUCTURED_SUFFIX_RE.fullmatch(normalized)
    if structured_match:
        suffix = structured_match.group("paren") or structured_match.group("underscore") or ""
        normalized = f"{structured_match.group('base')}.{suffix}"
    return normalized or None


@lru_cache(maxsize=8)
def _context_resolver(profile: str) -> ReferenceContextResolver:
    return ReferenceContextResolver(resolve_profile(profile).code)


def _has_reference_context(text: str, *, start: int, end: int, profile: str) -> bool:
    resolver = _context_resolver(profile)
    window_start = max(0, start - 48)
    window_end = min(len(text), end + 48)
    window = text[window_start:window_end]
    return resolver.detect_context(window).is_legal_reference


@lru_cache(maxsize=8)
def _adjacent_number_context(profile: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    resolved = resolve_profile(profile)
    aliases = get_numbering_aliases(
        profile=resolved.code, families=resolved.normalization_policy.get("context_families", [])
    )
    markers = "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True))
    before = re.compile(r"(?<!\w)(?:" + markers + r")\s*$", re.IGNORECASE)
    sources = "|".join(re.escape(a) for f in resolved.doc_families for a in f.aliases)
    after = re.compile(r"^\s+(?:" + sources + r")(?!\w)" if sources else r"(?!)", re.IGNORECASE)
    return before, after


def _has_number_context(text: str, *, start: int, end: int, profile: str) -> bool:
    before, after = _adjacent_number_context(resolve_profile(profile).code)
    return before.search(text[:start]) is not None or after.match(text[end:]) is not None


def _normalize_contextual_reference_suffixes(text: _TextView, *, profile: str) -> _TextView:
    def replace_superscript(match: re.Match[str]) -> str:
        if not _has_number_context(
            normalized.text, start=match.start(), end=match.end(), profile=profile
        ):
            return match.group(0)
        suffix = match.group("suffix").translate(_SUPERSCRIPT_TRANS)
        return f"{match.group('base')}.{suffix}"

    normalized = _normalize_structural_numbering_view(text, profile=profile)
    # Bare number next to a manifest source alias is a reference shorthand.
    normalized = normalized.sub(_SUPERSCRIPT_SUFFIX_RE, replace_superscript)

    def replace_structured(match: re.Match[str]) -> str:
        if not _has_number_context(
            normalized.text,
            start=match.start(),
            end=match.end(),
            profile=profile,
        ):
            return match.group(0)
        suffix = match.group("paren") or match.group("underscore") or ""
        return f"{match.group('base')}.{suffix}"

    if not resolve_profile(profile).normalization_policy.get("structured_suffix_context", False):
        return normalized
    return normalized.sub(_STRUCTURED_SUFFIX_RE, replace_structured)


def _drop_contextual_footnote_markers(text: _TextView, *, profile: str) -> _TextView:
    def replace_superscript_footnote(match: re.Match[str]) -> str:
        if _has_reference_context(text.text, start=match.start(), end=match.end(), profile=profile):
            return match.group(0)
        return match.group("word")

    normalized = text.sub(_WORD_SUPERSCRIPT_FOOTNOTE_RE, replace_superscript_footnote)

    def replace_bracket_footnote(match: re.Match[str]) -> str:
        if _has_reference_context(
            normalized.text,
            start=match.start(),
            end=match.end(),
            profile=profile,
        ):
            return match.group(0)
        return match.group("word")

    return normalized.sub(_WORD_BRACKET_FOOTNOTE_RE, replace_bracket_footnote)


def _repair_legal_article_footnotes(text: _TextView, *, profile: str) -> _TextView:
    if not repair_patterns(resolve_profile(profile).code):
        return text
    rules = repair_patterns(resolve_profile(profile).code)
    return text.sub(rules["article_bracket_footnote_re"], r"\1")


def _repair_split_legal_decimals(text: _TextView, *, profile: str) -> _TextView:
    if not repair_patterns(resolve_profile(profile).code):
        return text
    rules = repair_patterns(resolve_profile(profile).code)
    return text.sub(
        rules["legal_ref_split_decimal_re"],
        lambda match: f"{match.group(1)}.{match.group(2)}",
    )


def _repair_merged_article_decimals(text: _TextView, *, profile: str) -> _TextView:
    if not repair_patterns(resolve_profile(profile).code):
        return text

    rules = repair_patterns(resolve_profile(profile).code)
    normalized = text.sub(
        rules["legal_ref_merged_decimal_re"],
        lambda match: match.group(1) + approved_number(profile, "article", match.group("number")),
    )
    normalized = normalized.sub(
        rules["legal_chapter_merged_decimal_re"],
        lambda match: match.group(1) + approved_number(profile, "chapter", match.group("number")),
    )
    return normalized.sub(
        rules["legal_range_end_merged_decimal_re"],
        lambda match: match.group(1) + approved_number(profile, "range_end", match.group("number")),
    )


def _repair_heading_merged_legal_decimals(text: _TextView, *, profile: str) -> _TextView:
    if not repair_patterns(resolve_profile(profile).code):
        return text

    rules = repair_patterns(resolve_profile(profile).code)
    return text.sub(
        rules["heading_merged_decimal_re"],
        lambda match: (
            match.group("indent")
            + approved_number(profile, "chapter", match.group("number"))
            + match.group("tail")
        ),
    )


def _normalize_legal_view(view: _TextView, *, profile: str) -> _TextView:
    normalized = _normalize_extracted_view(view)
    if not normalized.text:
        return normalized
    normalized = _repair_legal_article_footnotes(normalized, profile=profile)
    normalized = _normalize_contextual_reference_suffixes(normalized, profile=profile)
    normalized = _drop_contextual_footnote_markers(normalized, profile=profile)
    normalized = _repair_split_legal_decimals(normalized, profile=profile)
    normalized = _repair_merged_article_decimals(normalized, profile=profile)
    normalized = _repair_heading_merged_legal_decimals(normalized, profile=profile)
    return normalized.strip()


def _normalize_reference_view(text: str, *, profile: str, track: bool = False) -> _TextView:
    view = _normalize_legal_view(_TextView.from_source(text or "", track=track), profile=profile)
    return view.sub(re.compile(r"\s+"), " ").strip()


def normalize_legal_text(text: str, *, profile: str = "generic") -> str:
    return _normalize_legal_view(_TextView.from_source(text or ""), profile=profile).text


def normalize_reference_text(text: str, *, profile: str = "generic") -> str:
    return _normalize_reference_view(text, profile=profile).text


__all__ = [
    "normalize_article_number",
    "normalize_legal_text",
    "normalize_reference_text",
    "normalize_numeric_scripts",
]
