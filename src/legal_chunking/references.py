"""Deterministic legal reference normalization helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

from legal_chunking.normalize import normalize_extracted_text
from legal_chunking.numbering_markers import build_numbering_marker_pattern
from legal_chunking.profiles import resolve_profile

_SUPERSCRIPT_TRANS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_SUBSCRIPT_TRANS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUPERSCRIPT_AFTER_DOT_RE = re.compile(r"(?<=\d)\.([⁰¹²³⁴⁵⁶⁷⁸⁹]+)")
_SUPERSCRIPT_AFTER_DIGIT_RE = re.compile(r"(?<=\d)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)")


def normalize_numeric_scripts(text: str) -> str:
    normalized = _SUPERSCRIPT_AFTER_DOT_RE.sub(
        lambda match: "." + match.group(1).translate(_SUPERSCRIPT_TRANS),
        text or "",
    )
    normalized = _SUPERSCRIPT_AFTER_DIGIT_RE.sub(
        lambda match: "." + match.group(1).translate(_SUPERSCRIPT_TRANS),
        normalized,
    )
    return normalized.translate(_SUBSCRIPT_TRANS)


@lru_cache(maxsize=8)
def _ru_numbering_rules(profile: str) -> dict[str, re.Pattern[str]]:
    article_keyword = build_numbering_marker_pattern(profile=profile, family="article_like")
    chapter_keyword = build_numbering_marker_pattern(profile=profile, family="chapter_like")
    point_keyword = build_numbering_marker_pattern(profile=profile, family="point_like")
    subpoint_keyword = build_numbering_marker_pattern(profile=profile, family="subpoint_like")
    paragraph_keyword = build_numbering_marker_pattern(profile=profile, family="paragraph_like")
    part_keyword = build_numbering_marker_pattern(profile=profile, family="part_like")
    legal_source_context = (
        r"(?:федеральн(?:ого|ым|ом)?\s+закона|закона|кодекса|"
        r"гк\s+рф|ук\s+рф|апк\s+рф|гпк\s+рф|нк\s+рф|коап\s+рф|"
        r"гражданского|уголовного|арбитражного|налогового|"
        r"конституции|конституционного\s+закона|[«\"])"
    )
    merged_article_followup_context = (
        r"(?:"
        + legal_source_context
        + r"|"
        + rf"{part_keyword}|{point_keyword}|{chapter_keyword}|{article_keyword}|ст\.?"
        + r")"
    )
    return {
        "article_bracket_footnote_re": re.compile(
            rf"(?i)\b({article_keyword}\s+\d{{2,3}})\s*\[\d+\]"
        ),
        "legal_ref_split_decimal_re": re.compile(
            r"(?i)\b("
            + (
                rf"(?:{article_keyword}|ст\.?|{point_keyword}|{part_keyword}|"
                rf"{subpoint_keyword}|{paragraph_keyword})"
            )
            + r"\s+\d{1,4}"
            + r")\s+(\d{1,3})(?=\s+(?:"
            + r"стат(?:ья|ьи|ье|ью|и)|ст\.?|"
            + legal_source_context
            + r"))"
        ),
        "legal_ref_merged_decimal_re": re.compile(
            rf"(?i)\b((?:{article_keyword}|ст\.?)\s+)(?P<number>\d{{4,5}})"
            rf"(?=(?:\s*(?:,|\)|;))?\s+{merged_article_followup_context})"
        ),
        "legal_chapter_merged_decimal_re": re.compile(
            rf"(?i)\b((?:{chapter_keyword})\s+)(?P<number>\d{{3,4}})"
            rf"(?=(?:\s*(?:,|\)|;))?\s+{merged_article_followup_context})"
        ),
        "legal_range_end_merged_decimal_re": re.compile(
            rf"(?i)\b((?:{point_keyword}|{subpoint_keyword}|{paragraph_keyword}|{part_keyword})\s+\d{{1,3}}\s*[–-]\s*)(?P<number>\d{{2}})"
            rf"(?=\s+{article_keyword}|(?=\s+ст\.?))"
        ),
        "heading_merged_decimal_re": re.compile(
            rf"(?im)^(?P<indent>\s*)(?P<number>\d{{3}})(?P<tail>\.?\s+(?:{legal_source_context}).*)$"
        ),
    }


def normalize_article_number(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_numeric_scripts(value).strip()
    return normalized or None


def _repair_legal_article_footnotes(text: str, *, profile: str) -> str:
    if resolve_profile(profile).code != "ru":
        return text
    rules = _ru_numbering_rules(profile)
    return rules["article_bracket_footnote_re"].sub(r"\1", text)


def _repair_split_legal_decimals(text: str, *, profile: str) -> str:
    if resolve_profile(profile).code != "ru":
        return text
    rules = _ru_numbering_rules(profile)
    return rules["legal_ref_split_decimal_re"].sub(
        lambda match: f"{match.group(1)}.{match.group(2)}",
        text,
    )


def _replace_with_decimal(prefix: str, raw_number: str, *, base_len: int) -> str:
    if len(raw_number) <= base_len:
        return prefix + raw_number
    base = raw_number[:base_len]
    suffix = raw_number[base_len:]
    if not suffix or (suffix.startswith("0") and len(raw_number) == 4):
        return prefix + raw_number
    return f"{prefix}{base}.{suffix}"


def _repair_merged_article_decimals(text: str, *, profile: str) -> str:
    if resolve_profile(profile).code != "ru":
        return text

    rules = _ru_numbering_rules(profile)
    normalized = rules["legal_ref_merged_decimal_re"].sub(
        lambda match: _replace_with_decimal(
            match.group(1),
            match.group("number"),
            base_len=3,
        ),
        text,
    )
    normalized = rules["legal_chapter_merged_decimal_re"].sub(
        lambda match: _replace_with_decimal(
            match.group(1),
            match.group("number"),
            base_len=2,
        ),
        normalized,
    )
    return rules["legal_range_end_merged_decimal_re"].sub(
        lambda match: (
            f"{match.group(1)}{match.group('number')[0]}.{match.group('number')[1]}"
            if not match.group("number").endswith("0")
            else match.group(0)
        ),
        normalized,
    )


def _repair_heading_merged_legal_decimals(text: str, *, profile: str) -> str:
    if resolve_profile(profile).code != "ru":
        return text

    rules = _ru_numbering_rules(profile)
    return rules["heading_merged_decimal_re"].sub(
        lambda match: (
            f"{match.group('indent')}{match.group('number')[:2]}.{match.group('number')[2]}"
            f"{match.group('tail')}"
            if not match.group("number").endswith("0")
            else match.group(0)
        ),
        text,
    )


def normalize_legal_text(text: str, *, profile: str = "generic") -> str:
    normalized = normalize_extracted_text(text or "")
    if not normalized:
        return ""
    normalized = normalize_numeric_scripts(normalized)
    normalized = _repair_legal_article_footnotes(normalized, profile=profile)
    normalized = _repair_split_legal_decimals(normalized, profile=profile)
    normalized = _repair_merged_article_decimals(normalized, profile=profile)
    normalized = _repair_heading_merged_legal_decimals(normalized, profile=profile)
    return normalized.strip()


def normalize_legal_query_text(text: str, *, profile: str = "generic") -> str:
    return re.sub(r"\s+", " ", normalize_legal_text(text or "", profile=profile)).strip()


def normalize_normalized_ref(ref: str | None) -> str | None:
    if ref is None:
        return None
    raw = ref.strip()
    if not raw:
        return None

    chunks: list[str] = []
    for token in raw.split("|"):
        key, sep, value = token.partition("=")
        if not sep:
            if token.strip():
                chunks.append(token.strip())
            continue
        normalized_key = key.strip()
        normalized_value = value.strip()
        if normalized_key in {"article", "paragraph", "part"}:
            normalized_value = normalize_article_number(normalized_value) or normalized_value
        chunks.append(
            f"{normalized_key}={normalized_value}" if normalized_key else normalized_value
        )
    normalized = "|".join(chunk for chunk in chunks if chunk)
    return normalized or None


def normalize_normalized_refs(refs: Iterable[str] | None) -> list[str]:
    normalized_refs: list[str] = []
    seen: set[str] = set()
    for ref in refs or ():
        normalized = normalize_normalized_ref(ref)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_refs.append(normalized)
    return normalized_refs


__all__ = [
    "normalize_article_number",
    "normalize_legal_query_text",
    "normalize_legal_text",
    "normalize_normalized_ref",
    "normalize_normalized_refs",
    "normalize_numeric_scripts",
]
