"""Predicate resolution: text → controlled ontology terms (T012).

Defines the :class:`PredicateResolver` protocol and a catalog-backed implementation. In production
the catalog is the embedded term index (research.md R1/R2); offline it is the fixture catalog.
Either way the resolver returns ranked :class:`PredicateCandidate`s — the model never authors a URI
(Constitution Principles II & IV).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from eol_genai_service.contract import PredicateCandidate


@dataclass(frozen=True)
class PredicateTerm:
    """A controlled predicate term plus the surface forms that map to it."""

    uri: str
    name: str
    type: str  # "measurement" | "association" | "categorical"
    aliases: tuple[str, ...]


class PredicateResolver(Protocol):
    def resolve(self, text: str) -> list[PredicateCandidate]: ...


class CatalogPredicateResolver:
    """Resolve against a fixed catalog by exact/alias match, scored and ranked."""

    def __init__(self, catalog: list[PredicateTerm]) -> None:
        self._catalog = catalog

    def resolve(self, text: str) -> list[PredicateCandidate]:
        needle = text.lower().strip()
        scored: list[PredicateCandidate] = []
        for term in self._catalog:
            score = _match_score(needle, (term.name, *term.aliases))
            if score > 0:
                scored.append(
                    PredicateCandidate(uri=term.uri, name=term.name, type=term.type, score=score)
                )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored


def _match_score(needle: str, forms: tuple[str, ...]) -> float:
    lowered = [f.lower() for f in forms]
    if needle in lowered:
        return 1.0
    # Substring either way → partial confidence.
    for f in lowered:
        if needle in f or f in needle:
            return 0.7
    return 0.0
