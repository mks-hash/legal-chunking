"""Optional source intervals carried through the actual normalization edits."""

from __future__ import annotations

import re
from array import array
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class _SourceMap:
    starts: array
    ends: array


@dataclass(slots=True, frozen=True)
class _TextView:
    text: str
    origins: _SourceMap | None = None

    @classmethod
    def from_source(cls, text: str, *, track: bool = False) -> _TextView:
        origins = (
            _SourceMap(array("Q", range(len(text))), array("Q", range(1, len(text) + 1)))
            if track
            else None
        )
        return cls(text, origins)

    def strip(self) -> _TextView:
        start = len(self.text) - len(self.text.lstrip())
        end = max(start, len(self.text.rstrip()))
        if start == 0 and end == len(self.text):
            return self
        origins = (
            _SourceMap(self.origins.starts[start:end], self.origins.ends[start:end])
            if self.origins is not None
            else None
        )
        return _TextView(self.text[start:end], origins)

    def replace(self, old: str, new: str) -> _TextView:
        if self.origins is None:
            return _TextView(self.text.replace(old, new))
        return self.sub(re.compile(re.escape(old)), lambda _: new)

    def strip_lines(self) -> _TextView:
        lines = self.text.split("\n")
        cleaned = [line.strip() for line in lines]
        result = "\n".join(cleaned)
        if result == self.text:
            return self
        if self.origins is None:
            return _TextView(result)
        starts, ends = array("Q"), array("Q")
        offset = 0
        for index, (line, value) in enumerate(zip(lines, cleaned, strict=True)):
            left = offset + len(line) - len(line.lstrip())
            right = left + len(value)
            starts.extend(self.origins.starts[left:right])
            ends.extend(self.origins.ends[left:right])
            if index + 1 < len(lines):
                boundary = offset + len(line)
                starts.append(self.origins.starts[boundary])
                ends.append(self.origins.ends[boundary])
            offset += len(line) + 1
        return _TextView(result, _SourceMap(starts, ends))

    def sub(
        self, pattern: re.Pattern[str], replacement: str | Callable[[re.Match[str]], str]
    ) -> _TextView:
        if self.origins is None:
            return _TextView(pattern.sub(replacement, self.text))
        starts, ends = array("Q"), array("Q")
        parts: list[str] = []
        previous = 0
        for match in pattern.finditer(self.text):
            start, end = match.span()
            value = replacement(match) if callable(replacement) else match.expand(replacement)
            original = match.group(0)
            if value == original:
                continue
            parts.append(self.text[previous:start])
            starts.extend(self.origins.starts[previous:start])
            ends.extend(self.origins.ends[previous:start])
            parts.append(value)
            # Preserve equal edges exactly. Only the changed middle gets a covering
            # interval; this is edit provenance, not fuzzy alignment with the input.
            prefix = 0
            while prefix < min(len(original), len(value)) and original[prefix] == value[prefix]:
                prefix += 1
            suffix = 0
            while (
                suffix < min(len(original) - prefix, len(value) - prefix)
                and original[-suffix - 1] == value[-suffix - 1]
            ):
                suffix += 1
            starts.extend(self.origins.starts[start : start + prefix])
            ends.extend(self.origins.ends[start : start + prefix])
            middle_length = len(value) - prefix - suffix
            left, right = start + prefix, end - suffix
            if middle_length:
                if left < right:
                    source_start, source_end = (
                        self.origins.starts[left],
                        self.origins.ends[right - 1],
                    )
                else:
                    # An insertion is anchored to its exact source boundary.
                    source_start = (
                        self.origins.starts[left]
                        if left < len(self.text)
                        else (self.origins.ends[-1] if self.text else 0)
                    )
                    source_end = source_start
                starts.extend(array("Q", [source_start]) * middle_length)
                ends.extend(array("Q", [source_end]) * middle_length)
            if suffix:
                starts.extend(self.origins.starts[end - suffix : end])
                ends.extend(self.origins.ends[end - suffix : end])
            previous = end
        if not parts:
            return self
        parts.append(self.text[previous:])
        starts.extend(self.origins.starts[previous:])
        ends.extend(self.origins.ends[previous:])
        return _TextView("".join(parts), _SourceMap(starts, ends))

    def source_range(self, start: int, end: int) -> tuple[int, int]:
        if self.origins is None or not 0 <= start < end <= len(self.text):
            raise ValueError("Source projection requires a non-empty mapped range")
        return self.origins.starts[start], self.origins.ends[end - 1]
