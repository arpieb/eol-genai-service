"""Repair-loop miss capture (T049 — research.md R8 / D1).

When the service cannot shape a query for a question it returns ``out_of_capability``; the pipeline
records that as a :class:`RepairMiss` here (only genuine gaps — never ``no_records``, which is a
valid answer per Principle VII, nor ``needs_clarification``, which is healthy disambiguation). This
is the live observability seam that turns capability gaps into data: :meth:`summary` ranks misses by
shape so the most common gaps are addressed first, and that ranking is what justifies wiring a
concrete runtime repair (e.g. ``missing-rollup`` retry) before writing speculative loop code.

This is the in-memory capture surface; a durable sink (log/store) plugs in behind :meth:`record`.
It is opt-in: ``PipelineDeps.miss_capture`` defaults to None, so capture is off unless a caller
provides a collector.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RepairMiss:
    """A case the repair rules could not fix — a candidate for a new rule."""

    question: str
    shape: str
    detail: str = ""


@dataclass
class MissCapture:
    misses: list[RepairMiss] = field(default_factory=list)

    def record(self, miss: RepairMiss) -> None:
        self.misses.append(miss)

    def summary(self) -> dict[str, int]:
        """Counts of misses by shape, to prioritize which rule to author next."""
        return dict(Counter(m.shape for m in self.misses))

    def __len__(self) -> int:
        return len(self.misses)
