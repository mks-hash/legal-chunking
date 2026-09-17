"""Heading detection runtime orchestration."""

from __future__ import annotations

from collections.abc import Callable

from legal_chunking.profiles import resolve_profile
from legal_chunking.tracing import TraceCollector, TraceStage

from .heading_admissibility import (
    article_heading_rejection_reason,
    format_label,
    looks_like_signature_name,
    numeric_heading_rejection_reason,
    paragraph_heading_rejection_reason,
    rule_heading_rejection_reason,
    section_heading_rejection_reason,
    structural_heading_rejection_reason,
    symbolic_heading_rejection_reason,
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
    trace: TraceCollector | None = None,
    offset: int | None = None,
) -> HeadingMatch | None:
    """Detect one canonical heading from a line of normalized text."""
    heading = (line or "").strip()
    if not heading:
        return None

    def reject(detector: str, reason: str) -> None:
        if trace is not None:
            trace.emit(
                TraceStage.DETECT,
                "heading_candidate_rejected",
                rule_id=f"heading.{detector}.{reason}",
                reason=reason,
                detector=detector,
                text=heading,
                offset=offset,
                profile=profile,
                chunk_policy=chunk_policy,
            )

    resolved_profile = resolve_profile(profile)
    heading_runtime = resolved_profile.runtime.heading

    prefixed_match = PREFIXED_EXPLICIT_HEADING_RE.match(heading)
    if prefixed_match:
        explicit_heading = detect_heading(
            prefixed_match.group("rest").strip(),
            profile=profile,
            chunk_policy=chunk_policy,
            trace=trace,
            offset=offset + prefixed_match.start("rest") if offset is not None else None,
        )
        if explicit_heading is not None:
            return explicit_heading

    for section_type, pattern in compile_heading_patterns(resolved_profile.code):
        match = pattern.match(heading)
        if not match:
            continue

        if section_type == "numeric_heading":
            return _detect_numeric_heading(heading, match, chunk_policy=chunk_policy, reject=reject)

        if section_type in {"roman_heading", "alpha_heading"}:
            return _detect_symbolic_section_heading(
                section_type,
                match,
                chunk_policy=chunk_policy,
                block_signature_names=heading_runtime.block_signature_names,
                reject=reject,
            )

        if chunk_policy == "guidance" and section_type in GUIDANCE_BLOCKED_KINDS:
            reject(section_type, "guidance_policy")
            return None

        title = match.groupdict().get("title") or ""
        if section_type == "section":
            reason = section_heading_rejection_reason(title)
            if reason is not None:
                reject(section_type, reason)
                continue
        reason = structural_heading_rejection_reason(section_type, title, chunk_policy=chunk_policy)
        if reason is not None:
            reject(section_type, reason)
            continue

        label = format_label(section_type, match, LABEL_PREFIX)
        if section_type == "schedule":
            return HeadingMatch(kind="other", label=label)
        if section_type == "article":
            reason = article_heading_rejection_reason(heading, title)
            if reason is not None:
                reject(section_type, reason)
                continue
            return HeadingMatch(
                kind="article",
                label=label,
                article_number=match.groupdict().get("num"),
            )
        if section_type == "rule":
            reason = rule_heading_rejection_reason(
                title, allow_long_titles=heading_runtime.allow_long_rule_titles
            )
            if reason is not None:
                reject(section_type, reason)
                continue
            return HeadingMatch(
                kind="article",
                label=label,
                article_number=match.groupdict().get("num"),
            )
        if section_type in {"clause", "paragraph"}:
            reason = paragraph_heading_rejection_reason(title)
            if reason is not None:
                reject(section_type, reason)
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
    reject: Callable[[str, str], None],
) -> HeadingMatch | None:
    raw_num = match.groupdict().get("num") or ""
    tail = match.groupdict().get("title") or ""
    reason = numeric_heading_rejection_reason(heading, raw_num, tail, chunk_policy=chunk_policy)
    if reason is not None:
        reject("numeric", reason)
        return None
    num = raw_num.rstrip(".")
    label = f"Section {num}" + (f". {tail}" if tail else "")
    depth = num.count(".")
    if depth == 0:
        return HeadingMatch(kind="section", label=label, detector_kind="numeric_heading")
    if chunk_policy == "guidance":
        reject("numeric", "guidance_depth")
        return None
    if depth == 1:
        return HeadingMatch(
            kind="article", label=label, article_number=num, detector_kind="numeric_heading"
        )
    return HeadingMatch(
        kind="clause", label=label, paragraph_number=num, detector_kind="numeric_heading"
    )


def _detect_symbolic_section_heading(
    section_type: str,
    match,
    *,
    chunk_policy: str,
    block_signature_names: bool,
    reject: Callable[[str, str], None],
) -> HeadingMatch | None:
    num = match.groupdict().get("num") or ""
    tail = match.groupdict().get("title") or ""
    if num != num.upper():
        reject(section_type, "lowercase_marker")
        return None
    if block_signature_names and len(num) == 1 and looks_like_signature_name(tail):
        reject(section_type, "signature_name")
        return None
    reason = symbolic_heading_rejection_reason(tail, chunk_policy=chunk_policy)
    if reason is not None:
        reject(section_type, reason)
        return None
    label = f"Section {num}" + (f". {tail}" if tail else "")
    _ = section_type
    return HeadingMatch(kind="section", label=label)


__all__ = ["detect_heading"]
