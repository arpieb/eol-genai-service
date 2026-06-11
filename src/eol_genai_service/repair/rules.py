"""Deterministic, versioned repair rules (T016 / T031 / T034 — Constitution Principle III).

The repair loop is rules-first, model-last (research.md R8). Each rule is a pure, independently
testable transform with a stable id+version. These encode domain fixes for known mis-shapings:

- ``categorical-as-numeric`` — a categorical predicate queried for a numeric measurement reads the
  wrong slot; the correct value slot is ``object_term`` (FR-005).
- ``flip-association-direction`` — an inverted association direction is flipped and re-asserted
  (FR-011); ``RO_0002471`` ("eaten by") is trivially invertible into nonsense.

Wiring these into the live repair loop (retry-on-empty/mismatch) is tracked separately; here they
are the versioned, tested primitives that loop will call.
"""

from __future__ import annotations

from dataclasses import dataclass

_OPPOSITE_DIRECTION = {
    "subject_to_object": "object_to_subject",
    "object_to_subject": "subject_to_object",
}

# Correct value slot for each predicate type (FR-005).
_SLOT_BY_TYPE = {
    "measurement": "normal_measurement",
    "categorical": "object_term",
    "association": "object_page",
}


@dataclass(frozen=True)
class RepairRule:
    id: str
    version: str
    description: str


REPAIR_RULES: tuple[RepairRule, ...] = (
    RepairRule("categorical-as-numeric", "1.0.0", "Read object_term for a categorical predicate"),
    RepairRule("flip-association-direction", "1.0.0", "Flip an inverted association direction"),
)


def rule_version(rule_id: str) -> str | None:
    """Return the registered version for ``rule_id``, or None if not registered."""
    for rule in REPAIR_RULES:
        if rule.id == rule_id:
            return rule.version
    return None


def correct_value_slot(predicate_type: str) -> str | None:
    """The value slot a predicate of this type should be read from (``categorical-as-numeric``)."""
    return _SLOT_BY_TYPE.get(predicate_type)


def flip_direction(direction: str) -> str:
    """Flip an association direction (``flip-association-direction``)."""
    return _OPPOSITE_DIRECTION[direction]
