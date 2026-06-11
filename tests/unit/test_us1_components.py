"""Unit tests for US-1 building blocks: shape template, extractor, resolvers."""

from eol_genai_service.extraction.extract import RuleBasedExtractor
from eol_genai_service.fixtures import (
    PREDICATE_CATALOG,
    TAXON_CATALOG,
    predicate_surface_forms,
    taxon_surface_forms,
)
from eol_genai_service.resolution.predicates import CatalogPredicateResolver
from eol_genai_service.resolution.taxa import CatalogTaxonResolver
from eol_genai_service.shapes.registry import shape_version
from eol_genai_service.shapes.single_fact import build_single_fact_query
from eol_genai_service.validator import validate


def test_single_fact_query_has_limit_uri_and_passes_validator():
    q = build_single_fact_query(328583, "VT_0001259", 100)
    assert "LIMIT 100" in q
    assert "VT_0001259" in q
    verdict = validate(q, {"VT_0001259"})
    assert verdict.ok, verdict.violations


def test_single_fact_query_uses_integer_page_id_no_injection():
    # page_id is coerced to int; a string with cypher in it cannot reach the query.
    q = build_single_fact_query(328583, "VT_0001259", 100)
    assert "page_id = 328583" in q


def test_shape_registry_versions_single_fact():
    assert shape_version("single_fact") is not None
    assert shape_version("n_hop_chain") is None  # US-7, not modeled yet


def test_extractor_recognizes_single_fact_and_novel():
    ex = RuleBasedExtractor(predicate_surface_forms(), taxon_surface_forms())
    intent = ex.extract("how heavy is a sea otter?")
    assert intent.shape == "single_fact"
    assert intent.taxon_refs == ("sea otter",)
    assert ex.extract("what is the airspeed of a swallow?").shape == "novel"


def test_predicate_resolver_ranks_exact_alias_top():
    r = CatalogPredicateResolver(PREDICATE_CATALOG)
    cands = r.resolve("mass")
    assert cands[0].uri == "VT_0001259"
    assert cands[0].score == 1.0


def test_taxon_resolver_resolves_vernacular_and_by_page_id():
    r = CatalogTaxonResolver(TAXON_CATALOG)
    cands = r.resolve("sea otter")
    assert cands[0].page_id == 328583
    assert r.by_page_id(328583).scientific_name == "Enhydra lutris"
    assert r.by_page_id(999999) is None
