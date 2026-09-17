"""Asset-backed numeric-script mechanics shared by structure and reference analysis."""

from __future__ import annotations

import re
from functools import lru_cache

from legal_chunking.errors import AssetConfigError
from legal_chunking.manifest import load_asset_json
from legal_chunking.numbering_markers import build_numbering_marker_pattern
from legal_chunking.profiles import resolve_profile
from legal_chunking.text_mapping import _TextView


@lru_cache(maxsize=1)
def numeric_script_rules() -> tuple[re.Pattern[str], dict[int, int], dict[int, int]]:
    policy = load_asset_json("normalization_policy/generic.v1.json")
    try:
        pattern = re.compile(policy["script_suffix_regex"])
        superscript = str.maketrans(policy["superscript_digits"] + "⁻", "0123456789-")
        subscript = str.maketrans(policy["subscript_digits"], "0123456789")
    except (KeyError, TypeError, ValueError, re.error) as exc:
        raise AssetConfigError("Invalid numeric script normalization policy") from exc
    return pattern, superscript, subscript


def normalize_number_scripts(value: str) -> str:
    suffix_pattern, superscript, subscript = numeric_script_rules()
    # Keep one dot after either a plain base digit or an existing decimal dot.
    pattern = re.compile(r"(?P<base>\d\.?)(?P<suffix>" + suffix_pattern.pattern + r")")
    normalized = pattern.sub(
        lambda m: m.group("base").rstrip(".") + "." + m.group("suffix").translate(superscript),
        value or "",
    )
    return normalized.translate(subscript)


@lru_cache(maxsize=8)
def numbering_context_pattern(profile: str) -> re.Pattern[str]:
    policy = resolve_profile(profile).normalization_policy
    families = policy.get("context_families", [])
    if not isinstance(families, list) or not all(isinstance(f, str) for f in families):
        raise AssetConfigError("Normalization context_families must be a list of strings")
    markers = "|".join(build_numbering_marker_pattern(profile=profile, family=f) for f in families)
    suffix, _, _ = numeric_script_rules()
    return re.compile(
        rf"(?P<marker>(?<!\w)(?:{markers})\s*)(?P<number>\d+(?:\.\d+)*(?:\.?(?:{suffix.pattern}))?)",
        re.IGNORECASE,
    )


def _normalize_structural_numbering_view(view: _TextView, *, profile: str) -> _TextView:
    # Require the adjacent marker; nearby legal prose does not prove numbering.
    return view.sub(
        numbering_context_pattern(profile),
        lambda m: m.group("marker") + normalize_number_scripts(m.group("number")),
    )


def normalize_structural_numbering(text: str, *, profile: str) -> str:
    return _normalize_structural_numbering_view(_TextView.from_source(text), profile=profile).text


@lru_cache(maxsize=8)
def repair_patterns(profile: str) -> dict[str, re.Pattern[str]]:
    resolved = resolve_profile(profile)
    policy = resolved.normalization_policy
    templates = policy.get("repair_patterns", {})
    if not isinstance(templates, dict):
        raise AssetConfigError("Normalization repair_patterns must be an object")
    source_terms = [re.escape(a) for f in resolved.doc_families for a in f.aliases]
    source_context = policy.get("legal_source_context_regex", r"(?!)")
    source_pattern = (
        "(?:" + str(source_context) + ("|" + "|".join(source_terms) if source_terms else "") + ")"
    )
    replacements = {"source_context": source_pattern}
    for family in policy.get("context_families", []):
        replacements[family] = build_numbering_marker_pattern(profile=profile, family=family)
    compiled: dict[str, re.Pattern[str]] = {}
    for name, template in templates.items():
        if not isinstance(template, str):
            raise AssetConfigError(f"Invalid normalization pattern {name}")
        for key, value in replacements.items():
            template = template.replace("{" + key + "}", value)
        try:
            compiled[name] = re.compile(template)
        except re.error as exc:
            raise AssetConfigError(f"Invalid normalization pattern {name}") from exc
    return compiled


def approved_number(profile: str, kind: str, number: str) -> str:
    policy = resolve_profile(profile).normalization_policy
    return policy.get("approved_merged_numbers", {}).get(kind, {}).get(number, number)
