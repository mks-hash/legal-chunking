"""Heading detection runtime orchestration."""

from __future__ import annotations

from legal_chunking.profiles import resolve_profile

from .heading_admissibility import (
    format_label,
    is_admissible_article_heading,
    is_admissible_numeric_heading,
    is_admissible_paragraph_heading,
    is_admissible_rule_heading,
    is_admissible_section_heading,
    is_admissible_structural_heading,
    is_admissible_symbolic_heading,
    looks_like_signature_name,
)
from .heading_patterns import compile_heading_patterns
from .heading_types import (
    GUIDANCE_BLOCKED_KINDS,
    LABEL_PREFIX,
    PREFIXED_EXPLICIT_HEADING_RE,
    HeadingMatch,
)


def detect_heading(
    line: str,
    *,
    profile: str = "generic",
    chunk_policy: str = "default",
) -> HeadingMatch | None:
    """Detect one canonical heading from a line of normalized text."""
    heading = (line or "").strip()
    if not heading:
        return None
    resolved_profile = resolve_profile(profile)
    heading_runtime = resolved_profile.runtime.heading

    prefixed_match = PREFIXED_EXPLICIT_HEADING_RE.match(heading)
    if prefixed_match:
        explicit_heading = detect_heading(
            prefixed_match.group("rest").strip(),
            profile=profile,
            chunk_policy=chunk_policy,
        )
        if explicit_heading is not None:
            return explicit_heading

    for section_type, pattern in compile_heading_patterns(resolved_profile.code):
        match = pattern.match(heading)
        if not match:
            continue

        if section_type == "numeric_heading":
            return _detect_numeric_heading(heading, match, chunk_policy=chunk_policy)

        if section_type in {"roman_heading", "alpha_heading"}:
            return _detect_symbolic_section_heading(
                section_type,
                match,
                chunk_policy=chunk_policy,
                block_signature_names=heading_runtime.block_signature_names,
            )

        if chunk_policy == "guidance" and section_type in GUIDANCE_BLOCKED_KINDS:
            return None

        title = match.groupdict().get("title") or ""
        if section_type == "section" and not is_admissible_section_heading(title):
            continue
        if not is_admissible_structural_heading(
            section_type,
            title,
            chunk_policy=chunk_policy,
        ):
            continue

        label = format_label(section_type, match, LABEL_PREFIX)
        if section_type == "schedule":
            return HeadingMatch(kind="other", label=label)
        if section_type == "article":
            if not is_admissible_article_heading(heading, title):
                continue
            return HeadingMatch(
                kind="article",
                label=label,
                article_number=match.groupdict().get("num"),
            )
        if section_type == "rule":
            if not is_admissible_rule_heading(
                title,
                allow_long_titles=heading_runtime.allow_long_rule_titles,
            ):
                continue
            return HeadingMatch(
                kind="article",
                label=label,
                article_number=match.groupdict().get("num"),
            )
        if section_type in {"clause", "paragraph"}:
            if not is_admissible_paragraph_heading(title):
                continue
            return HeadingMatch(
                kind=section_type,
                label=label,
                paragraph_number=match.groupdict().get("num"),
            )
        return HeadingMatch(kind=section_type, label=label)

    return None


def _detect_numeric_heading(
    heading: str,
    match,
    *,
    chunk_policy: str,
) -> HeadingMatch | None:
    raw_num = match.groupdict().get("num") or ""
    tail = match.groupdict().get("title") or ""
    if not is_admissible_numeric_heading(
        heading,
        raw_num,
        tail,
        chunk_policy=chunk_policy,
    ):
        return None
    num = raw_num.rstrip(".")
    label = f"Section {num}" + (f". {tail}" if tail else "")
    depth = num.count(".")
    if depth == 0:
        return HeadingMatch(kind="section", label=label)
    if chunk_policy == "guidance":
        return None
    if depth == 1:
        return HeadingMatch(kind="article", label=label, article_number=num)
    return HeadingMatch(kind="clause", label=label, paragraph_number=num)


def _detect_symbolic_section_heading(
    section_type: str,
    match,
    *,
    chunk_policy: str,
    block_signature_names: bool,
) -> HeadingMatch | None:
    num = match.groupdict().get("num") or ""
    tail = match.groupdict().get("title") or ""
    if num != num.upper():
        return None
    if block_signature_names and len(num) == 1 and looks_like_signature_name(tail):
        return None
    if not is_admissible_symbolic_heading(tail, chunk_policy=chunk_policy):
        return None
    label = f"Section {num}" + (f". {tail}" if tail else "")
    _ = section_type
    return HeadingMatch(kind="section", label=label)


__all__ = ["detect_heading"]
