"""Jurisdiction- and doc-family-aware legal reference parsing."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from legal_chunking.errors import AssetConfigError
from legal_chunking.manifest import ReferenceDocFamily, load_manifest
from legal_chunking.numbering_markers import get_numbering_family_aliases
from legal_chunking.profiles import (
    find_doc_family_alias_hits,
    resolve_doc_family_near,
    resolve_profile,
)
from legal_chunking.references import normalize_article_number, normalize_reference_text


@dataclass(slots=True, frozen=True)
class ParsedReference:
    raw: str
    scheme: str
    article_number: str | None
    paragraph_number: str | None
    part_number: str | None
    doc_family: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "raw": self.raw,
            "scheme": self.scheme,
            "article_number": self.article_number,
            "paragraph_number": self.paragraph_number,
            "part_number": self.part_number,
            "doc_family": self.doc_family,
        }

    def to_canonical_parts(self, *, jurisdiction: str) -> dict[str, str]:
        normalized_jurisdiction = resolve_profile(jurisdiction).code
        article_number = normalize_article_number(self.article_number)
        if not article_number:
            raise ValueError("ParsedReference must contain article_number for canonical parts")
        parts = {
            "jurisdiction": normalized_jurisdiction,
            "scheme": (self.scheme or "article").lower(),
            "article_number": article_number,
        }
        if self.doc_family:
            parts["doc_family"] = self.doc_family
        if self.paragraph_number:
            parts["paragraph_number"] = (
                normalize_article_number(self.paragraph_number) or self.paragraph_number
            )
        if self.part_number:
            parts["part_number"] = normalize_article_number(self.part_number) or self.part_number
        return parts


_ARTICLE_TOKEN = r"(?:[A-Za-z]\.?\s*)?\d+[A-Za-z0-9()./-]*"


@dataclass(slots=True, frozen=True)
class _PatternSpec:
    scheme: str
    pattern: re.Pattern[str]
    doc_family: str | None = None


def _build_asset_marker_patterns(
    *,
    profile: str,
    family: str,
    scheme: str,
) -> list[_PatternSpec]:
    compact_aliases, spaced_aliases = _split_marker_alias_groups(profile=profile, family=family)
    if not compact_aliases and not spaced_aliases:
        return []
    patterns: list[_PatternSpec] = []
    if compact_aliases:
        patterns.append(
            _PatternSpec(
                scheme=scheme,
                pattern=re.compile(
                    rf"(?<!\w)(?:{'|'.join(compact_aliases)})\s*(?P<article>{_ARTICLE_TOKEN})",
                    re.IGNORECASE,
                ),
            )
        )
    if spaced_aliases:
        patterns.append(
            _PatternSpec(
                scheme=scheme,
                pattern=re.compile(
                    rf"(?<!\w)(?:{'|'.join(spaced_aliases)})\s+(?P<article>{_ARTICLE_TOKEN})",
                    re.IGNORECASE,
                ),
            )
        )
    return patterns


def _compile_scoped_patterns_from_asset(profile: str) -> list[re.Pattern[str]]:
    payload = resolve_profile(profile).reference_patterns
    if not isinstance(payload, Mapping):
        raise AssetConfigError("Reference patterns payload must be an object")
    raw_patterns = payload.get("scoped_patterns", [])
    if not raw_patterns:
        return []
    if not isinstance(raw_patterns, list):
        raise AssetConfigError("Reference scoped_patterns payload must be a list")

    compiled: list[re.Pattern[str]] = []
    for item in raw_patterns:
        if not isinstance(item, Mapping):
            raise AssetConfigError("Reference scoped pattern entry must be an object")

        raw_fields = item.get("fields", {})
        if not isinstance(raw_fields, Mapping) or not raw_fields:
            raise AssetConfigError("Reference scoped pattern must define a non-empty fields object")

        field_patterns: dict[str, tuple[str, bool]] = {}
        for raw_name, raw_spec in raw_fields.items():
            field_name = str(raw_name).strip().lower()
            if field_name not in {"article", "paragraph", "part"}:
                raise AssetConfigError(f"Unsupported reference scoped field '{raw_name}'")
            if not isinstance(raw_spec, Mapping):
                raise AssetConfigError("Reference scoped field spec must be an object")

            family = str(raw_spec.get("family") or "").strip()
            number_pattern = str(raw_spec.get("number_pattern") or "").strip()
            required = bool(raw_spec.get("required", False))
            if not family or not number_pattern:
                raise AssetConfigError(
                    f"Reference scoped field '{field_name}' must define family and number_pattern"
                )

            marker_pattern = (
                _build_marker_prefix_pattern(profile=profile, family=family)
                if field_name == "article"
                else _build_marker_number_pattern(
                    profile=profile,
                    family=family,
                    number_pattern=number_pattern,
                )
            )
            pattern = (
                rf"{marker_pattern}(?P<{field_name}>{number_pattern})"
                if field_name == "article"
                else rf"(?P<{field_name}>{marker_pattern})"
            )
            field_patterns[field_name] = (pattern, required)

        order = item.get("order", ["article"])
        if not isinstance(order, list) or not order:
            raise AssetConfigError("Reference scoped pattern order must be a non-empty list")

        pattern_parts: list[str] = []
        for token in order:
            key = str(token).strip().lower()
            field_spec = field_patterns.get(key)
            if not field_spec:
                raise AssetConfigError(f"Unsupported reference scoped token '{token}'")
            part, required = field_spec
            if required:
                pattern_parts.append(part)
            else:
                pattern_parts.append(rf"(?:{part}\s*)?")

        compiled.append(re.compile(r"".join(pattern_parts), re.IGNORECASE))
    return compiled


def _split_marker_alias_groups(*, profile: str, family: str) -> tuple[list[str], list[str]]:
    raw_aliases = [
        alias
        for alias in get_numbering_family_aliases(profile=profile, family=family)
        if any(char.isalpha() for char in alias)
    ]
    compact_aliases = sorted(
        (re.escape(alias) for alias in raw_aliases if not alias[-1].isalnum()),
        key=len,
        reverse=True,
    )
    spaced_aliases = sorted(
        (re.escape(alias) for alias in raw_aliases if alias[-1].isalnum()),
        key=len,
        reverse=True,
    )
    return compact_aliases, spaced_aliases


def _build_marker_prefix_pattern(*, profile: str, family: str) -> str:
    compact_aliases, spaced_aliases = _split_marker_alias_groups(profile=profile, family=family)
    variants: list[str] = []
    if spaced_aliases:
        variants.append(rf"(?<!\w)(?:{'|'.join(spaced_aliases)})\s+")
    if compact_aliases:
        variants.append(rf"(?<!\w)(?:{'|'.join(compact_aliases)})\s*")
    if not variants:
        return r"(?!x)x"
    return "(?:" + "|".join(variants) + ")"


def _build_marker_number_pattern(*, profile: str, family: str, number_pattern: str) -> str:
    return _build_marker_prefix_pattern(profile=profile, family=family) + number_pattern


def _asset_generic_patterns_for_profile(profile: str) -> list[_PatternSpec]:
    patterns: list[_PatternSpec] = []
    patterns.extend(
        _build_asset_marker_patterns(
            profile=profile,
            family="article_like",
            scheme="article",
        )
    )
    patterns.extend(
        _build_asset_marker_patterns(
            profile=profile,
            family="section_like",
            scheme="section",
        )
    )
    return patterns


def _compile_pattern_specs(payload: object) -> list[_PatternSpec]:
    if not isinstance(payload, list):
        raise AssetConfigError("Reference pattern payload must be a list")
    specs: list[_PatternSpec] = []
    for item in payload:
        if not isinstance(item, Mapping):
            raise AssetConfigError("Reference pattern entry must be an object")
        scheme = str(item.get("scheme") or "").strip().lower()
        regex = str(item.get("regex") or "").strip()
        doc_family = str(item.get("doc_family") or "").strip().lower() or None
        if not scheme or not regex:
            raise AssetConfigError(f"Invalid reference pattern entry: {item}")
        specs.append(
            _PatternSpec(
                scheme=scheme,
                pattern=re.compile(regex, re.IGNORECASE),
                doc_family=doc_family,
            )
        )
    return specs


def _asset_reference_patterns(
    profile: str,
    *,
    doc_family: str | None = None,
    include_global: bool = True,
) -> list[_PatternSpec]:
    payload = resolve_profile(profile).reference_patterns
    if not isinstance(payload, Mapping):
        raise AssetConfigError("Reference patterns payload must be an object")

    patterns = _compile_pattern_specs(payload.get("patterns", [])) if include_global else []
    raw_doc_family_patterns = payload.get("doc_family_patterns", {})
    if not isinstance(raw_doc_family_patterns, Mapping):
        raise AssetConfigError("Reference doc_family_patterns payload must be an object")
    family = (doc_family or "").strip().lower()
    if family:
        patterns.extend(_compile_pattern_specs(raw_doc_family_patterns.get(family, [])))
    return patterns


def _jurisdiction_scheme_patterns(
    profile: str,
    *,
    doc_family: str | None = None,
) -> tuple[list[re.Pattern[str]], list[_PatternSpec]]:
    code = resolve_profile(profile).code
    family = (doc_family or "").strip().lower()
    scoped_patterns: list[re.Pattern[str]] = []
    generic_patterns: list[_PatternSpec] = []

    if code == "ru":
        scoped_patterns = _compile_scoped_patterns_from_asset(code)
    elif code == "us":
        generic_patterns.extend(_asset_generic_patterns_for_profile(code))
        generic_patterns.extend(
            _asset_reference_patterns(
                code,
                doc_family=family,
                include_global=not bool(family),
            )
        )
    elif code == "eu":
        generic_patterns.extend(_asset_generic_patterns_for_profile(code))
        generic_patterns.extend(_asset_reference_patterns(code, doc_family=family))
    elif code == "ae":
        generic_patterns.extend(_asset_generic_patterns_for_profile(code))
        generic_patterns.extend(_asset_reference_patterns(code, doc_family=family))
    else:
        generic_patterns.extend(_asset_generic_patterns_for_profile("generic"))
        generic_patterns.extend(_asset_reference_patterns("generic", doc_family=family))
    return scoped_patterns, generic_patterns


def _resolve_match_doc_family(
    *,
    alias_hits: tuple[object, ...],
    match: re.Match[str],
    profile: str,
    explicit_doc_family: str | None,
    inherited_doc_family: str | ReferenceDocFamily | None,
) -> str | None:
    if explicit_doc_family:
        return explicit_doc_family

    family = resolve_doc_family_near(
        profile,
        alias_hits,
        anchor_start=match.start(),
        anchor_end=match.end(),
    )
    if family is not None:
        return family.id

    if isinstance(inherited_doc_family, ReferenceDocFamily):
        return inherited_doc_family.id
    return inherited_doc_family


def _extract_number(raw: str | None) -> str | None:
    if not raw:
        return None
    normalized = normalize_article_number(raw)
    if not normalized:
        return None
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    return match.group(0) if match else None


def extract_references(
    text: str,
    *,
    profile: str = "generic",
    doc_family: str | None = None,
) -> list[ParsedReference]:
    resolved_profile = resolve_profile(profile)
    reference_config = load_manifest().profiles[resolved_profile.code].reference
    require_doc_family = bool(
        reference_config is not None
        and reference_config.enabled
        and reference_config.require_doc_family
    )
    inherited_family = doc_family or None
    inherited_family_id = (
        inherited_family.id
        if isinstance(inherited_family, ReferenceDocFamily)
        else inherited_family
    )
    text_norm = normalize_reference_text(text or "", profile=resolved_profile.code)
    alias_hits = find_doc_family_alias_hits(resolved_profile.code, text_norm.strip().lower())
    results: list[ParsedReference] = []
    seen: set[tuple[str, str | None, str | None, str | None, str | None]] = set()
    scoped_patterns, generic_patterns = _jurisdiction_scheme_patterns(
        resolved_profile.code,
        doc_family=doc_family,
    )

    def append_reference(ref: ParsedReference) -> None:
        if require_doc_family and not ref.doc_family:
            return
        key = (
            ref.scheme,
            ref.article_number,
            ref.paragraph_number,
            ref.part_number,
            ref.doc_family,
        )
        if key in seen:
            return
        seen.add(key)
        results.append(ref)

    for pattern in scoped_patterns:
        for match in pattern.finditer(text_norm):
            article = normalize_article_number(match.groupdict().get("article"))
            if not article:
                continue
            match_family = _resolve_match_doc_family(
                alias_hits=alias_hits,
                match=match,
                profile=resolved_profile.code,
                explicit_doc_family=inherited_family_id,
                inherited_doc_family=inherited_family,
            )
            append_reference(
                ParsedReference(
                    raw=match.group(0),
                    scheme="ru_article" if resolved_profile.code == "ru" else "section",
                    article_number=str(article),
                    paragraph_number=_extract_number(match.groupdict().get("paragraph")),
                    part_number=_extract_number(match.groupdict().get("part")),
                    doc_family=match_family,
                )
            )

    for spec in generic_patterns:
        for match in spec.pattern.finditer(text_norm):
            article = normalize_article_number(match.group("article"))
            if not article:
                continue
            match_family = _resolve_match_doc_family(
                alias_hits=alias_hits,
                match=match,
                profile=resolved_profile.code,
                explicit_doc_family=spec.doc_family or inherited_family_id,
                inherited_doc_family=inherited_family,
            )
            append_reference(
                ParsedReference(
                    raw=match.group(0),
                    scheme=spec.scheme,
                    article_number=str(article),
                    paragraph_number=None,
                    part_number=None,
                    doc_family=match_family,
                )
            )

    return results


__all__ = ["ParsedReference", "extract_references"]
