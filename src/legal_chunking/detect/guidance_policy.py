"""Profile-scoped guidance vocabulary; sequencing remains a Python mechanic."""

import re
from dataclasses import dataclass
from functools import lru_cache

from legal_chunking.errors import AssetConfigError
from legal_chunking.profiles import resolve_profile


@dataclass(frozen=True, slots=True)
class GuidancePolicy:
    point_start: re.Pattern[str]
    inline_point_start: re.Pattern[str]
    folio: re.Pattern[str]
    footnote: re.Pattern[str]
    citation_prefix: re.Pattern[str]
    excluded_prefix: re.Pattern[str]
    body_start: re.Pattern[str]
    max_forward_gap: int


@lru_cache(maxsize=8)
def guidance_policy(profile: str) -> GuidancePolicy:
    raw = resolve_profile(profile).normalization_policy.get("guidance", {})
    try:
        patterns = {
            name: re.compile(raw[name])
            for name in (
                "point_start",
                "inline_point_start",
                "folio",
                "footnote",
                "citation_prefix",
                "excluded_prefix",
                "body_start",
            )
        }
        if "num" not in patterns["point_start"].groupindex:
            raise ValueError("point_start must expose num")
        if "num" not in patterns["inline_point_start"].groupindex:
            raise ValueError("inline_point_start must expose num")
        gap = raw["max_forward_gap"]
        if isinstance(gap, bool) or not isinstance(gap, int) or gap < 1:
            raise ValueError("max_forward_gap must be a positive integer")
    except (KeyError, TypeError, ValueError, re.error) as exc:
        raise AssetConfigError("Invalid guidance normalization policy") from exc
    return GuidancePolicy(**patterns, max_forward_gap=gap)
