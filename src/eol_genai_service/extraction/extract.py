"""NL → QueryIntent extraction (T014).

Defines the :class:`Extractor` protocol (Constitution Principle V — the service model is scoped to
extraction). The production implementation uses Mellea-constrained decoding over a general Claude
model; :class:`RuleBasedExtractor` is a deterministic, offline stand-in driven by the known
fixture vocabulary so the pipeline is fully testable without an LLM. Both honor the same protocol,
so the live extractor drops in without changing the pipeline.
"""

from __future__ import annotations

from typing import Protocol

from eol_genai_service.extraction.intent import QueryIntent


class Extractor(Protocol):
    def extract(self, question: str) -> QueryIntent: ...


class RuleBasedExtractor:
    """Offline extractor: locates known taxon/predicate surface forms in the question.

    It recognizes the canonical single-fact shape ("how heavy is a sea otter?") by finding a
    measurement predicate phrase and a taxon mention. Anything it cannot map is ``shape="novel"``
    (routed to ``out_of_capability`` until US-7). Surface forms come from the catalog so the
    extractor and resolvers share one vocabulary.
    """

    def __init__(
        self,
        predicate_surface_forms: set[str],
        taxon_surface_forms: set[str],
    ) -> None:
        # Surface forms (lowercased), longest first so "sea otter" wins over "otter". The extractor
        # emits the matched *surface phrase* — it does NOT pre-resolve to one entity, so an
        # ambiguous phrase ("otter", "size") reaches the resolver and surfaces as multiple
        # candidates (US-6). Resolution, not extraction, owns disambiguation.
        self._predicates = _by_length_desc(predicate_surface_forms)
        self._taxa = _by_length_desc(taxon_surface_forms)

    def extract(self, question: str) -> QueryIntent:
        q = question.lower()
        predicate_ref = self._first_present(q, self._predicates)
        taxon_ref = self._first_present(q, self._taxa)

        # Count question (US-4): an attribute, no specific taxon; roll up sub-types (FR-006).
        if any(cue in q for cue in _COUNT_CUES):
            if predicate_ref:
                return QueryIntent(
                    shape="aggregate_count", predicate_refs=(predicate_ref,), rollup=True
                )
            return QueryIntent(shape="novel")

        # Lineage question (US-5): a taxon's ancestry, no predicate.
        if any(cue in q for cue in _LINEAGE_CUES):
            if taxon_ref:
                return QueryIntent(shape="lineage", taxon_refs=(taxon_ref,))
            return QueryIntent(shape="novel")

        # Single-hop attribute/association (US-1/2/3): concrete shape derived from predicate type.
        if predicate_ref and taxon_ref:
            return QueryIntent(
                shape="single_fact",
                taxon_refs=(taxon_ref,),
                predicate_refs=(predicate_ref,),
            )
        return QueryIntent(shape="novel")

    @staticmethod
    def _first_present(haystack: str, forms_longest_first: tuple[str, ...]) -> str | None:
        for form in forms_longest_first:
            if form in haystack:
                return form
        return None


def _by_length_desc(forms: set[str]) -> tuple[str, ...]:
    return tuple(sorted((f.lower() for f in forms), key=len, reverse=True))


# Question-form cues (generic English, not domain vocabulary — so they live in the extractor).
_COUNT_CUES = ("how many", "number of", "count of", "how much do we have")
_LINEAGE_CUES = ("ancestry", "lineage", "ancestors", "ancestor", "classification of", "phylogeny")
