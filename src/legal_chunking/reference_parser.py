"""Jurisdiction- and doc-family-aware legal reference parsing."""

from __future__ import annotations

import re
from bisect import bisect_left
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from itertools import product

from legal_chunking.errors import AssetConfigError
from legal_chunking.manifest import ReferenceDocFamily, load_manifest
from legal_chunking.numbering_markers import get_numbering_family_aliases
from legal_chunking.profiles import (
    ResolvedProfile,
    find_doc_family_alias_hits,
    resolve_doc_family_near,
    resolve_profile,
)
from legal_chunking.references import (
    _normalize_reference_view,
    normalize_article_number,
    normalize_numeric_scripts,
)

type _ReferenceKey = tuple[str, str | None, str | None, str | None, str | None]


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
        article_number = (
            normalize_article_number(self.article_number)
            if normalized_jurisdiction == "ru"
            else normalize_numeric_scripts(self.article_number or "").strip()
        )
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


def _compile_scoped_patterns_from_asset(profile: str) -> list[_PatternSpec]:
    payload = resolve_profile(profile).reference_patterns
    if not isinstance(payload, Mapping):
        raise AssetConfigError("Reference patterns payload must be an object")
    raw_patterns = payload.get("scoped_patterns", [])
    if not raw_patterns:
        return []
    if not isinstance(raw_patterns, list):
        raise AssetConfigError("Reference scoped_patterns payload must be a list")

    compiled: list[_PatternSpec] = []
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

            if raw_spec.get("range", False):
                syntax = resolve_profile(profile).numbering_markers.get("reference_syntax", {})
                ranges = syntax.get("range_separators", [])
                if not ranges or not all(isinstance(x, str) and x for x in ranges):
                    raise AssetConfigError("Reference ranges require range separators")
                range_pattern = "|".join(re.escape(x) for x in ranges)
                number_pattern = rf"{number_pattern}(?:\s*(?:{range_pattern})\s*{number_pattern})?"
            if raw_spec.get("coordinated_list", False):
                syntax = resolve_profile(profile).numbering_markers.get("reference_syntax", {})
                separators = syntax.get("list_separators", []) + syntax.get("list_conjunctions", [])
                if not separators or not all(isinstance(x, str) and x for x in separators):
                    raise AssetConfigError("Coordinated references require list separators")
                separator = "|".join(re.escape(x) for x in separators)
                number_pattern = rf"{number_pattern}(?:\s*(?:{separator})\s*{number_pattern})*"
            marker_pattern = _build_marker_prefix_pattern(profile=profile, family=family)
            pattern = rf"{marker_pattern}(?P<{field_name}>{number_pattern})"
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

        scheme = str(item.get("scheme") or "article")
        compiled.append(
            _PatternSpec(
                scheme=scheme,
                pattern=_compile_reference_regex(r"".join(pattern_parts) + r"(?!\w|\.\d|[-–—]\d)"),
            )
        )
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
            scheme=resolve_profile(profile)
            .reference_patterns.get("generic_schemes", {})
            .get("article_like", "article"),
        )
    )
    patterns.extend(
        _build_asset_marker_patterns(
            profile=profile,
            family="section_like",
            scheme=resolve_profile(profile)
            .reference_patterns.get("generic_schemes", {})
            .get("section_like", "section"),
        )
    )
    return patterns


def _compile_reference_regex(regex: str) -> re.Pattern[str]:
    try:
        return re.compile(regex, re.IGNORECASE)
    except re.error as exc:
        raise AssetConfigError("Invalid reference pattern regex") from exc


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
                pattern=_compile_reference_regex(regex),
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
    known_families = {family.id for family in resolve_profile(profile).doc_families}
    if any(spec.doc_family and spec.doc_family not in known_families for spec in patterns):
        raise AssetConfigError("Reference pattern must name a manifest document family")
    return patterns


def _jurisdiction_scheme_patterns(
    profile: str,
    *,
    doc_family: str | None = None,
) -> tuple[list[_PatternSpec], list[_PatternSpec]]:
    code = resolve_profile(profile).code
    scoped_patterns = _compile_scoped_patterns_from_asset(code)
    generic_patterns = _asset_generic_patterns_for_profile(code)
    generic_patterns.extend(
        _asset_reference_patterns(code, doc_family=doc_family, include_global=not bool(doc_family))
    )
    return scoped_patterns, generic_patterns


def _resolve_match_doc_family(
    *,
    alias_hits: tuple[object, ...],
    match: re.Match[str],
    profile: str,
    explicit_doc_family: str | None,
    inherited_doc_family: str | ReferenceDocFamily | None,
    pattern_doc_family: str | None = None,
) -> str | None:
    if pattern_doc_family:
        return pattern_doc_family
    family = resolve_doc_family_near(
        profile,
        alias_hits,
        anchor_start=match.start(),
        anchor_end=match.end(),
    )
    if family is not None:
        return family.id

    if explicit_doc_family:
        return explicit_doc_family
    if isinstance(inherited_doc_family, ReferenceDocFamily):
        return inherited_doc_family.id
    return inherited_doc_family


def _field_numbers(raw: str | None, profile: str) -> list[str | None]:
    if raw is None:
        return [None]
    syntax = resolve_profile(profile).numbering_markers.get("reference_syntax", {})
    separators = syntax.get("list_separators", []) + syntax.get("list_conjunctions", [])
    ranges = syntax.get("range_separators", [])
    parts = re.split("|".join(re.escape(x) for x in separators), raw) if separators else [raw]
    values: list[str | None] = []
    for part in parts:
        normalized = part.strip()
        for separator in ranges:
            normalized = re.sub(r"\s*" + re.escape(separator) + r"\s*", separator, normalized)
        values.append(normalize_article_number(normalized))
    return values


@dataclass(slots=True, frozen=True)
class ReferenceOccurrence:
    """One selected locator match, with input and normalized-view intervals."""

    start_offset: int
    end_offset: int
    raw: str
    normalized_start_offset: int
    normalized_end_offset: int
    references: tuple[ParsedReference, ...]


@dataclass(slots=True, frozen=True)
class ReferenceAnalysis:
    profile: str
    normalized_text: str
    occurrences: tuple[ReferenceOccurrence, ...]


@dataclass(slots=True, frozen=True)
class _ReferenceMatch:
    start: int
    end: int
    reference: ParsedReference
    scoped: bool


def _validate_reference_args(
    profile: str, doc_family: str | None
) -> tuple[ResolvedProfile, str | None]:
    resolved = resolve_profile(profile)
    if doc_family:
        doc_family = doc_family.strip().lower()
        if doc_family not in {f.id for f in resolved.doc_families}:
            raise ValueError(
                f"Unknown document family {doc_family!r} for profile {resolved.code!r}"
            )
    return resolved, doc_family


def _reference_key(
    ref: ParsedReference,
) -> _ReferenceKey:
    return ref.scheme, ref.article_number, ref.paragraph_number, ref.part_number, ref.doc_family


def _match_references(
    text_norm: str,
    *,
    profile: str = "generic",
    doc_family: str | None = None,
) -> Iterator[_ReferenceMatch]:
    resolved_profile, doc_family = _validate_reference_args(profile, doc_family)
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
    alias_hits = find_doc_family_alias_hits(resolved_profile.code, text_norm.strip().lower())
    scoped_patterns, generic_patterns = _jurisdiction_scheme_patterns(
        resolved_profile.code,
        doc_family=doc_family,
    )

    def make_match(
        match: re.Match[str], ref: ParsedReference, *, scoped: bool
    ) -> _ReferenceMatch | None:
        if require_doc_family and not ref.doc_family:
            return None
        return _ReferenceMatch(match.start(), match.end(), ref, scoped)

    candidates = [
        (spec, match) for spec in scoped_patterns for match in spec.pattern.finditer(text_norm)
    ]
    candidates.sort(key=lambda item: (item[1].start(), -len(item[1].group(0))))
    admitted_spans: list[tuple[int, int]] = []
    for spec, match in candidates:
        if admitted_spans and match.start() < admitted_spans[-1][1]:
            continue
        admitted_spans.append((match.start(), match.end()))
        match_family = _resolve_match_doc_family(
            alias_hits=alias_hits,
            match=match,
            profile=resolved_profile.code,
            explicit_doc_family=inherited_family_id,
            inherited_doc_family=inherited_family,
        )
        if inherited_family_id and match_family != inherited_family_id:
            continue
        fields = match.groupdict()
        for article, paragraph, part in product(
            _field_numbers(fields.get("article"), resolved_profile.code),
            _field_numbers(fields.get("paragraph"), resolved_profile.code),
            _field_numbers(fields.get("part"), resolved_profile.code),
        ):
            if inherited_family_id and match_family != inherited_family_id:
                continue
            record = make_match(
                match,
                ParsedReference(
                    raw=match.group(0),
                    scheme=spec.scheme,
                    article_number=article,
                    paragraph_number=paragraph,
                    part_number=part,
                    doc_family=match_family,
                ),
                scoped=True,
            )
            if record is not None:
                yield record

    admitted_starts = [start for start, _ in admitted_spans]
    for spec in generic_patterns:
        for match in spec.pattern.finditer(text_norm):
            index = bisect_left(admitted_starts, match.end()) - 1
            if index >= 0 and match.start() < admitted_spans[index][1]:
                continue
            article = normalize_numeric_scripts(match.group("article")).strip()
            if not article:
                continue
            match_family = _resolve_match_doc_family(
                alias_hits=alias_hits,
                match=match,
                profile=resolved_profile.code,
                explicit_doc_family=inherited_family_id,
                inherited_doc_family=inherited_family,
                pattern_doc_family=spec.doc_family,
            )
            if inherited_family_id and match_family != inherited_family_id:
                continue
            record = make_match(
                match,
                ParsedReference(
                    raw=match.group(0),
                    scheme=spec.scheme,
                    article_number=str(article),
                    paragraph_number=None,
                    part_number=None,
                    doc_family=match_family,
                ),
                scoped=False,
            )
            if record is not None:
                yield record


def extract_references(
    text: str, *, profile: str = "generic", doc_family: str | None = None
) -> list[ParsedReference]:
    """Preserve the legacy component deduplication and pattern traversal order."""
    resolved, doc_family = _validate_reference_args(profile, doc_family)
    view = _normalize_reference_view(text, profile=resolved.code)
    results: list[ParsedReference] = []
    seen = set()
    for match in _match_references(view.text, profile=resolved.code, doc_family=doc_family):
        key = _reference_key(match.reference)
        if key not in seen:
            seen.add(key)
            results.append(match.reference)
    return results


def _longest_component_spans(
    groups: dict[tuple[int, int], list[ParsedReference]],
) -> set[tuple[int, int, _ReferenceKey]]:
    # Only overlapping alternatives of the same component compete. Partition into
    # overlap clusters so repeated non-overlapping citations do not incur O(n²).
    by_key: dict[
        tuple[str, str | None, str | None, str | None, str | None], set[tuple[int, int]]
    ] = {}
    for span, refs in groups.items():
        for ref in refs:
            by_key.setdefault(_reference_key(ref), set()).add(span)
    retained = set()
    for key, spans in by_key.items():
        cluster: list[tuple[int, int]] = []
        max_end = -1

        def admit_cluster(cluster: list[tuple[int, int]], key: _ReferenceKey) -> None:
            admitted: list[tuple[int, int]] = []
            for start, end in sorted(cluster, key=lambda s: (-(s[1] - s[0]), s[0])):
                if not any(
                    start < other_end and end > other_start for other_start, other_end in admitted
                ):
                    admitted.append((start, end))
                    retained.add((start, end, key))

        for start, end in sorted(spans):
            if start >= max_end and cluster:
                admit_cluster(cluster, key)
                cluster = []
            cluster.append((start, end))
            max_end = max(max_end, end)
        admit_cluster(cluster, key)
    return retained


def analyze_references(
    text: str, *, profile: str = "generic", doc_family: str | None = None
) -> ReferenceAnalysis:
    """Retain input anchors and repeated occurrences with shared parser policy."""
    resolved, doc_family = _validate_reference_args(profile, doc_family)
    source = text or ""
    view = _normalize_reference_view(source, profile=resolved.code, track=True)
    groups: dict[tuple[int, int], list[ParsedReference]] = {}
    for match in _match_references(view.text, profile=resolved.code, doc_family=doc_family):
        refs = groups.setdefault((match.start, match.end), [])
        # Scoped list products preserve duplicate source members. Generic alternatives
        # matching the identical interval/component are not new physical occurrences.
        if match.scoped or not any(
            _reference_key(r) == _reference_key(match.reference) for r in refs
        ):
            refs.append(match.reference)
    retained = _longest_component_spans(groups)
    occurrences = []
    for (start, end), refs in sorted(groups.items()):
        admitted = tuple(ref for ref in refs if (start, end, _reference_key(ref)) in retained)
        if not admitted:
            continue
        source_start, source_end = view.source_range(start, end)
        occurrences.append(
            ReferenceOccurrence(
                source_start, source_end, source[source_start:source_end], start, end, admitted
            )
        )
    return ReferenceAnalysis(resolved.code, view.text, tuple(occurrences))


__all__ = [
    "ParsedReference",
    "ReferenceAnalysis",
    "ReferenceOccurrence",
    "analyze_references",
    "extract_references",
]
