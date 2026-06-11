"""US-7 novel multi-step integration tests (T040), offline fixtures.

A compositional question is answered by composing steps OR returned as out_of_capability — never a
fabricated answer. The composition half is exercised through the tool surface (the calling model's
orchestration path); the never-fabricate half through the NL pipeline.
"""

import pytest

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps, build_offline_tool_surface
from eol_genai_service.orchestration.pipeline import answer
from eol_genai_service.tools.surface import FORBIDDEN_METHODS, ChainResult, HopResult
from eol_genai_service.upstream.run_cypher import ValidatorRejection


# --- never fabricate: out_of_capability routing (T044) ----------------------------------------


def test_unmodeled_compositional_question_is_out_of_capability_not_a_guess():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="which pollinators visit plants that humans use?"), deps)
    assert result.outcome == "out_of_capability"  # never a plausible-looking wrong answer


# --- compose via the set-valued tool surface (T041/T042) --------------------------------------


def test_single_hop_is_set_valued_in_and_out():
    surface = build_offline_tool_surface()
    # A SET of inputs returns a SET — one hop over {otter, urchin} yields {urchin, kelp}.
    result = surface.single_hop({328583, 598454}, "RO_0002470", "subject_to_object")
    assert isinstance(result, HopResult)
    assert result.page_ids == frozenset({598454, 699999})
    assert result.truncated is False


def test_single_hop_rejects_invalid_direction():
    surface = build_offline_tool_surface()
    with pytest.raises(ValueError):
        surface.single_hop({328583}, "RO_0002470", "sideways")


def test_chaining_single_hops_composes_the_diet_chain():
    surface = build_offline_tool_surface()
    hop1 = surface.single_hop({328583}, "RO_0002470", "subject_to_object")  # otter → urchin
    hop2 = surface.single_hop(set(hop1.page_ids), "RO_0002470", "subject_to_object")  # → kelp
    assert hop2.page_ids == frozenset({699999})


def test_run_cypher_tool_is_validator_gated():
    surface = build_offline_tool_surface()
    # A write query must be refused before any execution (Principle II — no bypass).
    with pytest.raises(ValidatorRejection):
        surface.run_cypher("CREATE (n:Page) RETURN n LIMIT 1", set())


def test_surface_exposes_no_multi_hop_planner():
    surface = build_offline_tool_surface()
    for forbidden in FORBIDDEN_METHODS:
        assert not hasattr(surface, forbidden)  # planning stays with the calling model (V)
    for tool in (
        "resolve_predicate",
        "resolve_taxon",
        "run_cypher",
        "single_hop",
        "list_predicates",
        "get_schema",
        "n_hop_chain",
    ):
        assert callable(getattr(surface, tool))


def test_discovery_helpers():
    surface = build_offline_tool_surface()
    uris = {p.uri for p in surface.list_predicates()}
    assert "RO_0002470" in uris
    schema = surface.get_schema()
    assert "Page" in schema.node_types
    assert "object_page" in schema.value_slots


# --- compose server-side under a single LIMIT (T043) ------------------------------------------


def test_n_hop_chain_composes_server_side_under_one_limit():
    surface = build_offline_tool_surface()
    chain = surface.n_hop_chain(
        328583, [("RO_0002470", "subject_to_object"), ("RO_0002470", "subject_to_object")]
    )
    assert isinstance(chain, ChainResult)
    assert chain.page_ids == (699999,)
    assert chain.names == ("Macrocystis",)


def test_n_hop_chain_query_has_single_limit_and_passes_validator():
    from eol_genai_service.shapes.n_hop_chain import build_n_hop_chain_query
    from eol_genai_service.validator import validate

    q = build_n_hop_chain_query(
        328583, [("RO_0002470", "subject_to_object"), ("RO_0002470", "subject_to_object")], 100
    )
    assert q.count("LIMIT") == 1  # a single LIMIT for the whole chain (no per-hop truncation)
    assert q.count("WITH DISTINCT") == 2  # frontier carried forward each hop
    assert validate(q, {"RO_0002470"}).ok
