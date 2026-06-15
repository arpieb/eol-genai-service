"""Live T011 tests — real EOL + Ollama. Skipped unless EOL_JWT is set and Ollama is reachable.

Verifies the real grounding stack end-to-end: predicate resolution (embeddings over the
EOL-enumerated catalog → full body-mass URI), taxon resolution (search API → page id), and a real
single_fact answer mapped from live EOL data.
"""

import urllib.request

import pytest

from eol_genai_service.config import Settings, load_env
from eol_genai_service.contract import Predicate, Taxon
from eol_genai_service.resolution.embeddings import OllamaEmbedder
from eol_genai_service.resolution.predicate_index import (
    EmbeddingPredicateResolver,
    PredicateEmbeddingIndex,
    enumerate_predicate_terms,
)
from eol_genai_service.resolution.taxon_search import SearchApiTaxonResolver
from eol_genai_service.shapes.single_fact import build_single_fact_query
from eol_genai_service.upstream.client import EolCypherClient
from eol_genai_service.upstream.http_transport import HttpEolTransport
from eol_genai_service.upstream.mappers import map_single_fact_rows
from eol_genai_service.upstream.run_cypher import run_cypher

load_env()
_SETTINGS = Settings.from_env()
_BODY_MASS = "http://purl.obolibrary.org/obo/VT_0001259"


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_SETTINGS.eol_jwt and _ollama_up()), reason="needs EOL_JWT + Ollama"
)


@pytest.fixture(scope="module")
def predicate_resolver() -> EmbeddingPredicateResolver:
    embedder = OllamaEmbedder(_SETTINGS.embeddings_model_id)
    transport = HttpEolTransport(_SETTINGS)
    index = PredicateEmbeddingIndex.build(enumerate_predicate_terms(transport), embedder)
    return EmbeddingPredicateResolver(index, embedder)


def test_predicate_resolution_grounds_heavy_to_a_mass_or_weight_term(predicate_resolver):
    cands = predicate_resolver.resolve("how heavy is it")
    top = cands[0]
    assert top.uri.startswith("http://")  # full EOL URI
    assert top.score > 0.5
    # "heavy" grounds to a sensible mass/weight predicate (the catalog has both body mass and
    # weight; the model reasonably prefers "weight"). Exact term choice is a recall@k concern (C).
    assert "mass" in top.name.lower() or "weight" in top.name.lower(), top.name


def test_body_mass_uri_is_in_the_candidate_set(predicate_resolver):
    uris = {c.uri for c in predicate_resolver.resolve("body mass")}
    assert _BODY_MASS in uris


def test_taxon_search_resolves_scientific_name_to_page_id():
    cands = SearchApiTaxonResolver().resolve("Enhydra lutris")
    assert cands[0].score == 1.0
    assert isinstance(cands[0].page_id, int)


def test_single_fact_answers_from_real_eol_data():
    # Page 328598 has body-mass traits (confirmed by probe). The full pipeline path —
    # validator (full URI) → live transport → mapper — produces a quantitative statement.
    client = EolCypherClient(_SETTINGS, HttpEolTransport(_SETTINGS))
    query = build_single_fact_query(328598, _BODY_MASS, 5)
    upstream = run_cypher(query, {_BODY_MASS}, client)
    assert upstream.rows, "expected real body-mass rows from EOL"
    statements = map_single_fact_rows(
        upstream.rows,
        Taxon(page_id=328598, scientific_name="x"),
        Predicate(uri=_BODY_MASS, name="body mass", type="measurement"),
    )
    assert statements[0].value.kind == "quantitative"
    assert isinstance(statements[0].value.amount, float)
