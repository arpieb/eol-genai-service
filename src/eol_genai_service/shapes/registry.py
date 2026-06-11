"""Versioned shape registry (T016).

Anticipated query shapes are deterministic, versioned, testable templates (Principle III). The
registry maps a shape name to its current version, so a plan/answer can record exactly which
template produced a query. Only ``single_fact`` is registered so far (US-1).
"""

from __future__ import annotations

from eol_genai_service.shapes import single_fact

SHAPE_VERSIONS: dict[str, str] = {
    "single_fact": single_fact.VERSION,
}


def shape_version(shape: str) -> str | None:
    """Return the registered template version for ``shape``, or None if not modeled."""
    return SHAPE_VERSIONS.get(shape)
