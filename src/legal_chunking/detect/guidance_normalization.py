"""Guidance/review text normalization and artifact filtering."""

from __future__ import annotations

import re

RE_INLINE_GUIDANCE_POINT_START = re.compile(
    r"(?<!\n)[ \t]+(?P<num>\d{1,3})\.\s*\n(?=[A-ZА-ЯЁ])",
)
RE_STANDALONE_PAGE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
RE_FOOTNOTE_LINE = re.compile(r"^\s*\d{1,2}\s+[А-Яа-яA-Za-z].{0,160}$")


def normalize_guidance_text(text: str) -> str:
    prepared = RE_INLINE_GUIDANCE_POINT_START.sub(
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
        if is_guidance_page_artifact_line(stripped):
            continue
        kept.append(stripped)
    while kept and kept[-1] == "":
        kept.pop()
    if not kept:
        return ""
    return "\n".join(kept).strip()


def is_guidance_page_artifact_line(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped:
        return True
    if RE_STANDALONE_PAGE_NUMBER.match(stripped):
        return True
    if RE_FOOTNOTE_LINE.match(stripped):
        lower = stripped.lower()
        if "далее" in lower or "сноск" in lower:
            return True
    return False


__all__ = [
    "is_guidance_page_artifact_line",
    "normalize_guidance_text",
]
