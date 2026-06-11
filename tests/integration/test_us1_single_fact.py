"""US-1 single-fact integration tests (T019), driven by the offline-fixture pipeline.

Independent test (spec): "how heavy is a sea otter?" returns the body-mass measurement with units
and source; a taxon with no mass record returns an explicit no_records.
"""

from eol_genai_service.config import Settings
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps, fixture_transport
from eol_genai_service.orchestration.pipeline import PipelineDeps, answer
from eol_genai_service.resolution.predicates import CatalogPredicateResolver
from eol_genai_service.resolution.taxa import CatalogTaxonResolver
from eol_genai_service.extraction.extract import RuleBasedExtractor
from eol_genai_service.fixtures import (
    PREDICATE_CATALOG,
    TAXON_CATALOG,
    predicate_surface_forms,
    taxon_surface_forms,
)
from eol_genai_service.upstream.client import EolCypherClient


def test_sea_otter_mass_returns_quantitative_answer_with_provenance():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)

    assert result.outcome == "answer"
    assert len(result.statements) == 1
    stmt = result.statements[0]
    assert stmt.subject.scientific_name == "Enhydra lutris"
    assert stmt.predicate.uri == "VT_0001259"
    assert stmt.value.kind == "quantitative"
    assert stmt.value.amount == 25.0
    assert stmt.value.units == "kg"
    assert stmt.provenance.resource["name"] == "PanTHERIA"
    assert result.truncated is False


def test_taxon_with_no_mass_record_returns_no_records():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="how heavy is a raccoon?"), deps)
    assert result.outcome == "no_records"


def test_unmodeled_question_is_out_of_capability_not_a_guess():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what is the meaning of life?"), deps)
    assert result.outcome == "out_of_capability"


def test_upstream_failure_maps_to_upstream_unavailable():
    def failing(query, fmt):
        raise TimeoutError("eol down")

    settings = Settings()
    deps = PipelineDeps(
        extractor=RuleBasedExtractor(predicate_surface_forms(), taxon_surface_forms()),
        predicate_resolver=CatalogPredicateResolver(PREDICATE_CATALOG),
        taxon_resolver=CatalogTaxonResolver(TAXON_CATALOG),
        client=EolCypherClient(settings, failing),
        settings=settings,
    )
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    assert result.outcome == "upstream_unavailable"


def test_fixture_transport_returns_rows_for_known_pair():
    rows = fixture_transport(
        "MATCH ... uri:'VT_0001259' ... WHERE p.page_id = 328583 ... LIMIT 100", "cypher"
    )
    assert rows and rows[0]["units"] == "kg"
