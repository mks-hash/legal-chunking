"""Admissibility rules for heading candidates."""

from __future__ import annotations

import re


def format_label(section_type: str, match: re.Match[str], label_prefix: dict[str, str]) -> str:
    num = match.groupdict().get("num") or ""
    title = (match.groupdict().get("title") or "").strip()
    if num:
        prefix = label_prefix.get(section_type, section_type.capitalize())
        return f"{prefix} {num}" + (f". {title}" if title else "")
    return match.group(0).strip()


def has_explicit_numeric_heading_marker(line: str, num_token: str) -> bool:
    heading = (line or "").strip()
    normalized_num = (num_token or "").strip()
    if not heading or not normalized_num:
        return False
    if "." in normalized_num:
        return True
    suffix = heading[len(normalized_num) :].lstrip()
    return bool(suffix[:1] in {".", ")"})


def numeric_heading_rejection_reason(
    line: str, num_token: str, title: str, *, chunk_policy: str
) -> str | None:
    normalized_num = (num_token or "").strip()
    tail = (title or "").strip()
    if not normalized_num or not tail:
        return "missing_number_or_title"
    if not has_explicit_numeric_heading_marker(line, normalized_num):
        return "missing_marker"
    if len(tail) > 120:
        return "title_too_long"
    words = tail.split()
    if len(words) > 14:
        return "too_many_words"
    punctuation_hits = len(re.findall("[.!?;:]", tail))
    if punctuation_hits > 1:
        return "excess_punctuation"
    if tail[:1].islower():
        return "lowercase_title"
    if _starts_with_weak_pronoun(words):
        return "weak_pronoun"
    if chunk_policy in {"guidance", "case_law"} and len(words) > 10:
        return "policy_word_limit"
    return None


def is_admissible_numeric_heading(
    line: str, num_token: str, title: str, *, chunk_policy: str
) -> bool:
    return (
        numeric_heading_rejection_reason(line, num_token, title, chunk_policy=chunk_policy) is None
    )


def symbolic_heading_rejection_reason(title: str, *, chunk_policy: str) -> str | None:
    tail = (title or "").strip()
    if not tail:
        return "missing_title"
    if len(tail) > 120:
        return "title_too_long"
    words = tail.split()
    if len(words) > 14:
        return "too_many_words"
    punctuation_hits = len(re.findall("[.!?;:]", tail))
    if punctuation_hits > 1:
        return "excess_punctuation"
    if tail[:1].islower():
        return "lowercase_title"
    if chunk_policy in {"guidance", "case_law"} and len(words) > 10:
        return "policy_word_limit"
    return None


def is_admissible_symbolic_heading(title: str, *, chunk_policy: str) -> bool:
    return symbolic_heading_rejection_reason(title, chunk_policy=chunk_policy) is None


def looks_like_signature_name(title: str) -> bool:
    tail = (title or "").strip()
    if not tail:
        return False
    tokens = tail.split()
    if not 1 <= len(tokens) <= 3:
        return False
    return all(
        re.fullmatch("(?:[A-Z]\\.){1,3}|[A-Z][A-Z-]+", token) is not None for token in tokens
    )


def structural_heading_rejection_reason(
    section_type: str, title: str, *, chunk_policy: str
) -> str | None:
    if section_type not in {"part", "chapter", "section", "schedule"}:
        return None
    tail = (title or "").strip()
    if not tail:
        return None
    return symbolic_heading_rejection_reason(tail, chunk_policy=chunk_policy)


def is_admissible_structural_heading(section_type: str, title: str, *, chunk_policy: str) -> bool:
    return (
        structural_heading_rejection_reason(section_type, title, chunk_policy=chunk_policy) is None
    )


def article_heading_rejection_reason(line: str, title: str) -> str | None:
    tail = (title or "").strip()
    if tail.startswith("("):
        return "parenthesized_title"
    if tail and (not any(char.isalpha() for char in tail)):
        return "nonalphabetic_title"
    if tail.upper().startswith("TFEU"):
        return "tfeu_citation"
    if re.search("\\barticle\\s+\\d+\\(", line, re.IGNORECASE):
        return "parenthesized_citation"
    if tail and (not is_admissible_symbolic_heading(tail, chunk_policy="default")):
        return "phrase_not_admissible"
    return None


def is_admissible_article_heading(line: str, title: str) -> bool:
    return article_heading_rejection_reason(line, title) is None


def rule_heading_rejection_reason(title: str, *, allow_long_titles: bool) -> str | None:
    tail = (title or "").strip()
    if not tail:
        return "missing_title"
    if tail.startswith("("):
        return "parenthesized_title"
    words = tail.split()
    punctuation_hits = len(re.findall("[.!?;:]", tail))
    max_chars = 140 if allow_long_titles else 120
    max_words = 20 if allow_long_titles else 14
    max_punctuation = 4 if allow_long_titles else 1
    if len(tail) > max_chars:
        return "title_too_long"
    if len(words) > max_words:
        return "too_many_words"
    if punctuation_hits > max_punctuation:
        return "excess_punctuation"
    if tail[:1].islower():
        return "lowercase_title"
    if _starts_with_weak_pronoun(words):
        return "weak_pronoun"
    return None


def is_admissible_rule_heading(title: str, *, allow_long_titles: bool) -> bool:
    return rule_heading_rejection_reason(title, allow_long_titles=allow_long_titles) is None


def section_heading_rejection_reason(title: str) -> str | None:
    return _phrase_heading_rejection_reason(title)


def is_admissible_section_heading(title: str) -> bool:
    return section_heading_rejection_reason(title) is None


def paragraph_heading_rejection_reason(title: str) -> str | None:
    return _phrase_heading_rejection_reason(title)


def is_admissible_paragraph_heading(title: str) -> bool:
    return paragraph_heading_rejection_reason(title) is None


def _phrase_heading_rejection_reason(title: str) -> str | None:
    tail = (title or "").strip()
    if not tail:
        return "missing_title"
    if tail.startswith(("(", ",", ";", ":", "-", "—")):
        return "separator_prefix"
    reason = symbolic_heading_rejection_reason(tail, chunk_policy="default")
    if reason is not None:
        return reason
    return "weak_pronoun" if _starts_with_weak_pronoun(tail.split()) else None


def _is_admissible_phrase_heading(title: str) -> bool:
    return _phrase_heading_rejection_reason(title) is None


def _starts_with_weak_pronoun(words: list[str]) -> bool:
    if not words:
        return False
    return words[0].casefold() in {
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "they",
        "their",
        "he",
        "she",
        "we",
        "you",
    }


__all__ = [
    "format_label",
    "has_explicit_numeric_heading_marker",
    "is_admissible_article_heading",
    "is_admissible_numeric_heading",
    "is_admissible_paragraph_heading",
    "is_admissible_rule_heading",
    "is_admissible_section_heading",
    "is_admissible_structural_heading",
    "is_admissible_symbolic_heading",
    "looks_like_signature_name",
]
