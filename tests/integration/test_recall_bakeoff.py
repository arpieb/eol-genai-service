"""Live recall@k bake-off for predicate grounding (research R2). Skipped without EOL_JWT+Ollama.

Builds the real embedded catalog and measures how often the correct EOL URI is in the top-k for a
labeled set of phrases. Prints the metrics (use `-s`) and asserts a regression bar.
"""

import urllib.request

import pytest

from eol_genai_service.config import Settings, load_env
from eol_genai_service.eval.labeled_predicates import LABELED
from eol_genai_service.eval.recall import evaluate
from eol_genai_service.resolution.embeddings import OllamaEmbedder
from eol_genai_service.resolution.predicate_index import (
    EmbeddingPredicateResolver,
    PredicateEmbeddingIndex,
    enumerate_predicate_terms,
)
from eol_genai_service.upstream.http_transport import HttpEolTransport

load_env()
_SETTINGS = Settings.from_env()


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
def graded():
    embedder = OllamaEmbedder(_SETTINGS.embeddings_model_id)
    terms = enumerate_predicate_terms(HttpEolTransport(_SETTINGS))
    name_to_uri = {t.name.lower(): t.uri for t in terms if t.name}
    resolver = EmbeddingPredicateResolver(
        PredicateEmbeddingIndex.build(terms, embedder), embedder, k=10
    )
    labeled_uris = [
        (q, name_to_uri[name.lower()]) for q, name in LABELED if name.lower() in name_to_uri
    ]
    return evaluate(resolver.resolve, labeled_uris)


def test_recall_bakeoff(graded):
    print("\nLOCAL mxbai-embed-large:", graded.summary())
    if graded.misses:
        print("misses:", graded.misses)
    # Regression bar (local default must keep grounding well). recall@5 is the operative bar
    # because the pipeline asks for clarification among the top contenders rather than blind-picking.
    # Observed: R@1=50%, R@3=86%, R@5=86%, mean_correct_score=0.78. Bars set with headroom for
    # embedding-model nondeterminism.
    assert graded.recall_at_5 >= 0.80, graded.summary()
    assert graded.recall_at_3 >= 0.70, graded.summary()


def test_correct_scores_support_the_live_threshold(graded):
    # The live confidence gate is 0.5; the correct candidate should typically clear it.
    assert graded.mean_correct_score > 0.5, graded.summary()
