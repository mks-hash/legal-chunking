"""Guidance/review text normalization and artifact filtering."""

from __future__ import annotations

from array import array

from legal_chunking.text_mapping import _SourceMap, _TextView

from .guidance_policy import guidance_policy


def _normalize_guidance_view(view: _TextView, *, profile: str = "generic") -> _TextView:
    policy = guidance_policy(profile)
    prepared = view.sub(
        policy.inline_point_start,
        lambda match: f"\n{match.group('num')}. ",
    )
    raw_lines = prepared.text.split("\n")
    kept: list[str] = []
    kept_spans: list[tuple[int, int] | None] = []
    offset = 0
    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
                kept_spans.append(None)
            offset += len(raw_line) + 1
            continue
        if is_guidance_page_artifact_line(stripped, profile=profile):
            offset += len(raw_line) + 1
            continue
        left = offset + len(raw_line) - len(raw_line.lstrip())
        right = left + len(stripped)
        kept.append(stripped)
        kept_spans.append((left, right))
        offset += len(raw_line) + 1
    while kept and kept[-1] == "":
        kept.pop()
        kept_spans.pop()
    if not kept:
        return _TextView("", _SourceMap(array("Q"), array("Q")) if prepared.origins else None)
    joined = "\n".join(kept)
    if prepared.origins is None:
        return _TextView(joined).strip()

    starts, ends = array("Q"), array("Q")
    last_end = prepared.origins.ends[0] if prepared.origins.ends else 0
    for index, span in enumerate(kept_spans):
        if index > 0:
            starts.append(last_end)
            ends.append(last_end)
        if span is not None:
            left, right = span
            starts.extend(prepared.origins.starts[left:right])
            ends.extend(prepared.origins.ends[left:right])
            if right > left:
                last_end = prepared.origins.ends[right - 1]
    return _TextView(joined, _SourceMap(starts, ends)).strip()


def normalize_guidance_text(text: str, *, profile: str = "generic") -> str:
    return _normalize_guidance_view(_TextView.from_source(text or ""), profile=profile).text


def is_guidance_page_artifact_line(line: str, *, profile: str = "generic") -> bool:
    policy = guidance_policy(profile)
    stripped = (line or "").strip()
    if not stripped:
        return True
    if policy.folio.fullmatch(stripped):
        return True
    if policy.footnote.fullmatch(stripped):
        return True
    return False


__all__ = [
    "is_guidance_page_artifact_line",
    "normalize_guidance_text",
]
