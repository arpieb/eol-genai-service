"""Taxon resolution: name → EOL page_id (T013).

Prefers identifier-based lookup to reduce homonym error (FR-003). Production resolves via EOL's
own page/search lookup; offline resolves against the fixture catalog. Returns ranked
:class:`TaxonCandidate`s; ``by_page_id`` supports the stateless disambiguation resubmit (FR-014).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from eol_genai_service.contract import Taxon, TaxonCandidate


@dataclass(frozen=True)
class TaxonRecord:
    page_id: int
    scientific_name: str
    vernaculars: tuple[str, ...]


class TaxonResolver(Protocol):
    def resolve(self, name: str) -> list[TaxonCandidate]: ...

    def by_page_id(self, page_id: int) -> Taxon | None: ...


class CatalogTaxonResolver:
    """Resolve against a fixed catalog by scientific name or vernacular, scored and ranked."""

    def __init__(self, catalog: list[TaxonRecord]) -> None:
        self._catalog = catalog
        self._by_id = {r.page_id: r for r in catalog}

    def resolve(self, name: str) -> list[TaxonCandidate]:
        needle = name.lower().strip()
        scored: list[TaxonCandidate] = []
        for rec in self._catalog:
            forms = (rec.scientific_name, *rec.vernaculars)
            score = _match_score(needle, forms)
            if score > 0:
                scored.append(
                    TaxonCandidate(
                        page_id=rec.page_id,
                        scientific_name=rec.scientific_name,
                        vernacular_names=[{"name": v} for v in rec.vernaculars],
                        score=score,
                    )
                )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored

    def by_page_id(self, page_id: int) -> Taxon | None:
        rec = self._by_id.get(page_id)
        if rec is None:
            return None
        return Taxon(
            page_id=rec.page_id,
            scientific_name=rec.scientific_name,
            vernacular_names=[{"name": v} for v in rec.vernaculars],
        )


def _match_score(needle: str, forms: tuple[str, ...]) -> float:
    lowered = [f.lower() for f in forms]
    if needle in lowered:
        return 1.0
    for f in lowered:
        if needle in f or f in needle:
            return 0.7
    return 0.0
