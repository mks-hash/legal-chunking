"""Structured trace models for explainable parser and chunk decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class TraceEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class TraceReport:
    events: tuple[TraceEvent, ...] = ()


@dataclass(slots=True)
class TraceCollector:
    _events: list[TraceEvent] = field(default_factory=list)

    def emit(self, event_type: str, **data: Any) -> None:
        self._events.append(TraceEvent(type=event_type, data=data))

    def to_report(self) -> TraceReport:
        return TraceReport(events=tuple(self._events))


__all__ = ["TraceCollector", "TraceEvent", "TraceReport"]
