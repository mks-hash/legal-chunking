"""Deterministic legal reference normalization helpers."""

from __future__ import annotations

import re
from functools import lru_cache

from legal_chunking.legal_normalization import (
    approved_number,
    normalize_number_scripts,
    normalize_structural_numbering,
    numeric_script_rules,
    repair_patterns,
)
from legal_chunking.normalize import normalize_extracted_text
from legal_chunking.numbering_markers import get_numbering_aliases
from legal_chunking.profiles import resolve_profile
from legal_chunking.reference_context import ReferenceContextResolver

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


def _normalize_contextual_reference_suffixes(text: str, *, profile: str) -> str:
    def replace_superscript(match: re.Match[str]) -> str:
        if not _has_number_context(text, start=match.start(), end=match.end(), profile=profile):
            return match.group(0)
        suffix = match.group("suffix").translate(_SUPERSCRIPT_TRANS)
        return f"{match.group('base')}.{suffix}"

    normalized = normalize_structural_numbering(text, profile=profile)
    # Bare number next to a manifest source alias is a reference shorthand.
    normalized = _SUPERSCRIPT_SUFFIX_RE.sub(replace_superscript, normalized)

    def replace_structured(match: re.Match[str]) -> str:
        if not _has_number_context(
            normalized,
            start=match.start(),
            end=match.end(),
            profile=profile,
        ):
            return match.group(0)
        suffix = match.group("paren") or match.group("underscore") or ""
        return f"{match.group('base')}.{suffix}"

    if not resolve_profile(profile).normalization_policy.get("structured_suffix_context", False):
        return normalized
    return _STRUCTURED_SUFFIX_RE.sub(replace_structured, normalized)


def _drop_contextual_footnote_markers(text: str, *, profile: str) -> str:
    def replace_superscript_footnote(match: re.Match[str]) -> str:
        if _has_reference_context(text, start=match.start(), end=match.end(), profile=profile):
            return match.group(0)
        return match.group("word")

    normalized = _WORD_SUPERSCRIPT_FOOTNOTE_RE.sub(replace_superscript_footnote, text)

    def replace_bracket_footnote(match: re.Match[str]) -> str:
        if _has_reference_context(
            normalized,
            start=match.start(),
            end=match.end(),
            profile=profile,
        ):
            return match.group(0)
        return match.group("word")

    return _WORD_BRACKET_FOOTNOTE_RE.sub(replace_bracket_footnote, normalized)


def _repair_legal_article_footnotes(text: str, *, profile: str) -> str:
    if not repair_patterns(resolve_profile(profile).code):
        return text
    rules = repair_patterns(resolve_profile(profile).code)
    return rules["article_bracket_footnote_re"].sub(r"\1", text)


def _repair_split_legal_decimals(text: str, *, profile: str) -> str:
    if not repair_patterns(resolve_profile(profile).code):
        return text
    rules = repair_patterns(resolve_profile(profile).code)
    return rules["legal_ref_split_decimal_re"].sub(
        lambda match: f"{match.group(1)}.{match.group(2)}",
        text,
    )


def _repair_merged_article_decimals(text: str, *, profile: str) -> str:
    if not repair_patterns(resolve_profile(profile).code):
        return text

    rules = repair_patterns(resolve_profile(profile).code)
    normalized = rules["legal_ref_merged_decimal_re"].sub(
        lambda match: match.group(1) + approved_number(profile, "article", match.group("number")),
        text,
    )
    normalized = rules["legal_chapter_merged_decimal_re"].sub(
        lambda match: match.group(1) + approved_number(profile, "chapter", match.group("number")),
        normalized,
    )
    return rules["legal_range_end_merged_decimal_re"].sub(
        lambda match: match.group(1) + approved_number(profile, "range_end", match.group("number")),
        normalized,
    )


def _repair_heading_merged_legal_decimals(text: str, *, profile: str) -> str:
    if not repair_patterns(resolve_profile(profile).code):
        return text

    rules = repair_patterns(resolve_profile(profile).code)
    return rules["heading_merged_decimal_re"].sub(
        lambda match: (
            match.group("indent")
            + approved_number(profile, "chapter", match.group("number"))
            + match.group("tail")
        ),
        text,
    )


def normalize_legal_text(text: str, *, profile: str = "generic") -> str:
    normalized = normalize_extracted_text(text or "")
    if not normalized:
        return ""
    normalized = _repair_legal_article_footnotes(normalized, profile=profile)
    normalized = _normalize_contextual_reference_suffixes(normalized, profile=profile)
    normalized = _drop_contextual_footnote_markers(normalized, profile=profile)
    normalized = _repair_split_legal_decimals(normalized, profile=profile)
    normalized = _repair_merged_article_decimals(normalized, profile=profile)
    normalized = _repair_heading_merged_legal_decimals(normalized, profile=profile)
    return normalized.strip()


def normalize_reference_text(text: str, *, profile: str = "generic") -> str:
    return re.sub(r"\s+", " ", normalize_legal_text(text or "", profile=profile)).strip()


__all__ = [
    "normalize_article_number",
    "normalize_legal_text",
    "normalize_reference_text",
    "normalize_numeric_scripts",
]
