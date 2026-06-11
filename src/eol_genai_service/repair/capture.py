"""Repair-loop miss capture (T049 — research.md R8).

The repair loop is rules-first; when no deterministic rule resolves a case, that miss is captured
so the rule set can be grown over time. This is the in-memory capture surface; a durable sink
(log/store) plugs in behind :meth:`record`. :meth:`summary` ranks misses by shape so the most
common gaps are addressed first.
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
