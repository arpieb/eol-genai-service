"""SC-005 truncation suite (T046): the truncated flag is always set, never silent — incl. per-hop.

When a result cap is hit the answer (or hop) MUST flag ``truncated``; no partial result is ever
returned silently.
"""

from eol_genai_service.config import Settings
from eol_genai_service.contract import AnswerRequest, Predicate
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
from eol_genai_service.tools.surface import DEFAULT_SCHEMA, ToolSurface
from eol_genai_service.upstream.client import EolCypherClient


def _measurement_rows(n):
    return [
        {
            "amount": float(i),
            "units": "kg",
            "resource_id": 1,
            "resource_name": "X",
            "citation": None,
        }
        for i in range(n)
    ]


def _deps_with(transport, cap):
    settings = Settings(result_cap=cap)
    return PipelineDeps(
        extractor=RuleBasedExtractor(predicate_surface_forms(), taxon_surface_forms()),
        predicate_resolver=CatalogPredicateResolver(PREDICATE_CATALOG),
        taxon_resolver=CatalogTaxonResolver(TAXON_CATALOG),
        client=EolCypherClient(settings, transport),
        settings=settings,
    )


def test_answer_flags_truncation_when_cap_is_hit():
    deps = _deps_with(lambda q, fmt: _measurement_rows(5), cap=2)
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    assert result.outcome == "answer"
    assert result.truncated is True
    assert len(result.statements) == 2  # capped, not all 5


def test_answer_is_not_flagged_when_under_cap():
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), build_offline_deps())
    assert result.truncated is False


def test_truncated_field_is_always_present_on_answers():
    payload = answer(
        AnswerRequest(question="how heavy is a sea otter?"), build_offline_deps()
    ).model_dump_json()
    assert "truncated" in payload


def test_single_hop_flags_per_hop_truncation():
    # A hop returning more partners than the cap must surface truncated — never silently partial.
    transport = lambda q, fmt: [{"partner_page_id": i} for i in range(5)]  # noqa: E731
    deps = _deps_with(transport, cap=2)
    predicates = [Predicate(uri=t.uri, name=t.name, type=t.type) for t in PREDICATE_CATALOG]
    surface = ToolSurface(deps, predicates, DEFAULT_SCHEMA)
    hop = surface.single_hop({328583}, "RO_0002470", "subject_to_object")
    assert hop.truncated is True
    assert len(hop.page_ids) == 2
