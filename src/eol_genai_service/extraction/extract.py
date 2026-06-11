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
        predicate_surface_forms: dict[str, str],
        taxon_surface_forms: dict[str, str],
    ) -> None:
        # Map: surface form (lowercased) -> canonical ref. Longest forms matched first so
        # "body mass" wins over "mass".
        self._predicates = predicate_surface_forms
        self._taxa = taxon_surface_forms

    def extract(self, question: str) -> QueryIntent:
        q = question.lower()
        predicate_ref = self._longest_match(q, self._predicates)
        taxon_ref = self._longest_match(q, self._taxa)

        if predicate_ref and taxon_ref:
            return QueryIntent(
                shape="single_fact",
                taxon_refs=(taxon_ref,),
                predicate_refs=(predicate_ref,),
            )
        return QueryIntent(shape="novel")

    @staticmethod
    def _longest_match(haystack: str, forms: dict[str, str]) -> str | None:
        best: str | None = None
        best_len = 0
        for form, ref in forms.items():
            if form in haystack and len(form) > best_len:
                best, best_len = ref, len(form)
        return best
