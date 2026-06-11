"""US-8 no-data integration tests (T027).

A valid, well-formed question whose upstream result is empty returns an explicit ``no_records``
(FR-010) — returned once, with no retry loop, and distinct from ``upstream_unavailable`` (FR-013).
"""

from eol_genai_service.config import Settings
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.extraction.extract import RuleBasedExtractor
from eol_genai_service.fixtures import (
    PREDICATE_CATALOG,
    TAXON_CATALOG,
    build_offline_deps,
    predicate_surface_forms,
    taxon_surface_forms,
)
from eol_genai_service.orchestration.pipeline import PipelineDeps, answer
from eol_genai_service.resolution.predicates import CatalogPredicateResolver
from eol_genai_service.resolution.taxa import CatalogTaxonResolver
from eol_genai_service.upstream.client import EolCypherClient


class CountingEmptyTransport:
    """A transport that always returns an empty result and counts how often it is called."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, query: str, fmt: str) -> list[dict[str, object]]:
        self.calls += 1
        return []


def _deps_with(transport) -> PipelineDeps:
    settings = Settings()
    return PipelineDeps(
        extractor=RuleBasedExtractor(predicate_surface_forms(), taxon_surface_forms()),
        predicate_resolver=CatalogPredicateResolver(PREDICATE_CATALOG),
        taxon_resolver=CatalogTaxonResolver(TAXON_CATALOG),
        client=EolCypherClient(settings, transport),
        settings=settings,
    )


def test_empty_upstream_returns_no_records():
    deps = build_offline_deps()
    # Raccoon resolves confidently but has no recorded body mass in the fixtures.
    result = answer(AnswerRequest(question="how heavy is a raccoon?"), deps)
    assert result.outcome == "no_records"


def test_empty_result_is_returned_once_with_no_retry():
    transport = CountingEmptyTransport()
    deps = _deps_with(transport)
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    assert result.outcome == "no_records"
    assert transport.calls == 1  # empty is a valid answer — never retried


def test_no_records_is_distinct_from_upstream_unavailable():
    empty = answer(
        AnswerRequest(question="how heavy is a sea otter?"), _deps_with(CountingEmptyTransport())
    )

    def failing(query, fmt):
        raise TimeoutError("eol down")

    unavailable = answer(AnswerRequest(question="how heavy is a sea otter?"), _deps_with(failing))
    assert empty.outcome == "no_records"
    assert unavailable.outcome == "upstream_unavailable"
    assert empty.outcome != unavailable.outcome
