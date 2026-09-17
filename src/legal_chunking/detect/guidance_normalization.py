"""Guidance/review text normalization and artifact filtering."""

from __future__ import annotations

from .guidance_policy import guidance_policy


def normalize_guidance_text(text: str, *, profile: str = "generic") -> str:
    policy = guidance_policy(profile)
    prepared = policy.inline_point_start.sub(
        lambda match: f"\n{match.group('num')}. ",
        text or "",
    )
    kept: list[str] = []
    for raw_line in prepared.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if is_guidance_page_artifact_line(stripped, profile=profile):
            continue
        kept.append(stripped)
    while kept and kept[-1] == "":
        kept.pop()
    if not kept:
        return ""
    return "\n".join(kept).strip()


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
