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


def is_admissible_numeric_heading(
    line: str,
    num_token: str,
    title: str,
    *,
    chunk_policy: str,
) -> bool:
    normalized_num = (num_token or "").strip()
    tail = (title or "").strip()
    if not normalized_num or not tail:
        return False
    if not has_explicit_numeric_heading_marker(line, normalized_num):
        return False
    if len(tail) > 120:
        return False
    words = tail.split()
    if len(words) > 14:
        return False
    punctuation_hits = len(re.findall(r"[.!?;:]", tail))
    if punctuation_hits > 1:
        return False
    if tail[:1].islower():
        return False
    if _starts_with_weak_pronoun(words):
        return False
    if chunk_policy in {"guidance", "case_law"} and len(words) > 10:
        return False
    return True


def is_admissible_symbolic_heading(title: str, *, chunk_policy: str) -> bool:
    tail = (title or "").strip()
    if not tail:
        return False
    if len(tail) > 120:
        return False
    words = tail.split()
    if len(words) > 14:
        return False
    punctuation_hits = len(re.findall(r"[.!?;:]", tail))
    if punctuation_hits > 1:
        return False
    if tail[:1].islower():
        return False
    if chunk_policy in {"guidance", "case_law"} and len(words) > 10:
        return False
    return True


def looks_like_signature_name(title: str) -> bool:
    tail = (title or "").strip()
    if not tail:
        return False
    tokens = tail.split()
    if not (1 <= len(tokens) <= 3):
        return False
    return all(
        re.fullmatch(r"(?:[A-Z]\.){1,3}|[A-Z][A-Z-]+", token) is not None for token in tokens
    )


def is_admissible_structural_heading(
    section_type: str,
    title: str,
    *,
    chunk_policy: str,
) -> bool:
    if section_type not in {"part", "chapter", "section", "schedule"}:
        return True
    tail = (title or "").strip()
    if not tail:
        return True
    return is_admissible_symbolic_heading(tail, chunk_policy=chunk_policy)


def is_admissible_article_heading(line: str, title: str) -> bool:
    tail = (title or "").strip()
    if tail.startswith("("):
        return False
    if tail and not any(char.isalpha() for char in tail):
        return False
    if tail.upper().startswith("TFEU"):
        return False
    if re.search(r"\barticle\s+\d+\(", line, re.IGNORECASE):
        return False
    if tail and not is_admissible_symbolic_heading(tail, chunk_policy="default"):
        return False
    return True


def is_admissible_rule_heading(title: str, *, allow_long_titles: bool) -> bool:
    tail = (title or "").strip()
    if not tail:
        return False
    if tail.startswith("("):
        return False
    words = tail.split()
    punctuation_hits = len(re.findall(r"[.!?;:]", tail))
    max_chars = 140 if allow_long_titles else 120
    max_words = 20 if allow_long_titles else 14
    max_punctuation = 4 if allow_long_titles else 1
    if len(tail) > max_chars:
        return False
    if len(words) > max_words:
        return False
    if punctuation_hits > max_punctuation:
        return False
    if tail[:1].islower():
        return False
    if _starts_with_weak_pronoun(words):
        return False
    return True


def is_admissible_section_heading(title: str) -> bool:
    return _is_admissible_phrase_heading(title)


def is_admissible_paragraph_heading(title: str) -> bool:
    return _is_admissible_phrase_heading(title)


def _is_admissible_phrase_heading(title: str) -> bool:
    tail = (title or "").strip()
    if not tail:
        return False
    if tail.startswith(("(", ",", ";", ":", "-", "—")):
        return False
    if not is_admissible_symbolic_heading(tail, chunk_policy="default"):
        return False
    return not _starts_with_weak_pronoun(tail.split())


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
