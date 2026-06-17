"""Recorded-EOL CI tests (live-integration §6).

Replays **real** EOL responses (captured to tests/fixtures/eol_cassettes/) so the EOL-facing
pipeline — validator (full URIs), the attribute shape, neo4j→contract mapping, and the search-API
taxon resolver — runs in CI with no JWT and no network. Re-record the cassettes by running the
recorder against live EOL when the shapes change.
"""

from eol_genai_service.config import Settings
from eol_genai_service.contract import Predicate, Taxon
from eol_genai_service.shapes.attribute import build_attribute_query
from eol_genai_service.upstream.client import EolCypherClient
from eol_genai_service.upstream.mappers import map_attribute_rows
from eol_genai_service.upstream.run_cypher import run_cypher
from support import BODY_MASS, HABITAT, load_cassette, recorded_search_resolver, replay_transport

_TRANSPORT = load_cassette("transport.json")
_SEARCH = load_cassette("search.json")


def _client() -> EolCypherClient:
    return EolCypherClient(Settings(), replay_transport(_TRANSPORT))


def test_recorded_body_mass_answers_quantitatively():
    query = build_attribute_query(328598, BODY_MASS, 5)
    upstream = run_cypher(query, {BODY_MASS}, _client())  # validator runs on the full URI
    assert upstream.rows
    statements = map_attribute_rows(
        upstream.rows,
        Taxon(page_id=328598, scientific_name="x"),
        Predicate(uri=BODY_MASS, name="body mass", type="measurement"),
    )
    assert statements[0].value.kind == "quantitative"
    assert statements[0].value.amount == 5525.0  # real recorded EOL value
    assert statements[0].provenance.resource["name"] == "Smith et al 2011"


def test_recorded_habitat_answers_categorically():
    # habitat is measurement-typed in EOL but carries an object_term value (the type-gap path).
    query = build_attribute_query(47098272, HABITAT, 5)
    upstream = run_cypher(query, {HABITAT}, _client())
    statements = map_attribute_rows(
        upstream.rows,
        Taxon(page_id=47098272, scientific_name="x"),
        Predicate(uri=HABITAT, name="habitat", type="measurement"),
    )
    assert statements[0].value.kind == "categorical"
    assert statements[0].value.term.name == "marine benthic"  # real recorded EOL value


def test_recorded_search_resolves_scientific_name():
    cands = recorded_search_resolver(_SEARCH).resolve("Enhydra lutris")
    assert cands[0].score == 1.0  # exact title match in the real recorded results
    assert isinstance(cands[0].page_id, int)


def test_recorded_common_name_is_ambiguous():
    cands = recorded_search_resolver(_SEARCH).resolve("sea otter")
    assert all(c.score < 0.5 for c in cands)  # noisy common name → clarification (real data)
