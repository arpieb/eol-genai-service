"""Deterministic, versioned repair rules (T016 — Constitution Principle III).

The repair loop is rules-first, model-last (research.md R8). Each rule is a pure, independently
testable transform with a stable id+version.

**Status (2026-06): the live runtime repair *loop* is deferred (D1).** Two of the three repairs
originally designed here are now pre-empted *deterministically at build time*, which is strictly
better than retry-after-failure (Principle III):

- ``categorical-as-numeric`` (read ``object_term`` instead of ``normal_measurement``) is obviated by
  the dual-slot ``attribute`` shape, which reads **both** value slots in one query, so a categorical
  predicate never empties from reading the wrong slot. Removed.
- ``flip-association-direction`` is obviated by ``shapes.association.association_direction(uri)``,
  which asserts the correct direction *before* the query is built. Removed.

That leaves ``missing-rollup`` as the one repair a future runtime loop would still apply (add the
``parent_term|synonym_of*0..`` traversal when a category under-counts its sub-types, FR-006). It is
kept here as the versioned primitive that loop will call. The loop itself is wired only once
``MissCapture`` (capture.py, now live in the pipeline) shows a concrete case that justifies it — see
research.md R8 for the staged ramp.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepairRule:
    id: str
    version: str
    description: str


REPAIR_RULES: tuple[RepairRule, ...] = (
    RepairRule("missing-rollup", "1.0.0", "Add the parent_term roll-up traversal for a category"),
)

# The roll-up traversal injected when a category query under-counts its sub-types (FR-006).
ROLLUP_TRAVERSAL = "-[:parent_term|synonym_of*0..]->"


def rollup_traversal() -> str:
    """The traversal to add when a query is missing roll-up (``missing-rollup``)."""
    return ROLLUP_TRAVERSAL


def rule_version(rule_id: str) -> str | None:
    """Return the registered version for ``rule_id``, or None if not registered."""
    for rule in REPAIR_RULES:
        if rule.id == rule_id:
            return rule.version
    return None
