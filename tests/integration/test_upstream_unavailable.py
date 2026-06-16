"""FR-013 upstream-unavailable integration test (T052).

Timeout / 5xx / transport error → an explicit ``upstream_unavailable`` outcome, distinct from
``no_records`` (FR-010) and from internal errors; bounded retry with backoff, never a tight loop.
"""

from dataclasses import replace

import httpx

from support import offline_deps
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import (
    build_offline_deps,
)
from eol_genai_service.orchestration.pipeline import answer
from eol_genai_service.resolution.taxon_search import SearchApiTaxonResolver


def _deps_with(transport, max_retries=2):
    return offline_deps(transport, upstream_max_retries=max_retries)


def test_timeout_maps_to_upstream_unavailable():
    def failing(q, fmt):
        raise TimeoutError("eol timed out")

    result = answer(AnswerRequest(question="how heavy is a sea otter?"), _deps_with(failing))
    assert result.outcome == "upstream_unavailable"
    assert "timed out" in result.detail


def test_retry_is_bounded_not_a_tight_loop():
    calls = {"n": 0}

    def failing(q, fmt):
        calls["n"] += 1
        raise ConnectionError("5xx")

    answer(AnswerRequest(question="how heavy is a sea otter?"), _deps_with(failing, max_retries=2))
    assert calls["n"] == 3  # initial + exactly 2 retries; bounded


def test_search_api_error_during_resolution_maps_to_upstream_unavailable():
    # The taxon search API is also an upstream: a 429/5xx while resolving the taxon must surface as
    # upstream_unavailable (not crash), the same outcome as a failed EOL Cypher round-trip.
    def rate_limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    search = SearchApiTaxonResolver(
        client=httpx.Client(transport=httpx.MockTransport(rate_limited))
    )
    deps = replace(build_offline_deps(), taxon_resolver=search)
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    assert result.outcome == "upstream_unavailable"
    assert "search" in result.detail.lower()


def test_embedding_backend_error_during_resolution_maps_to_upstream_unavailable(monkeypatch):
    # The embedding backend (predicate grounding) is also an upstream: if it's down while resolving
    # the predicate, the request surfaces upstream_unavailable, not a crash.
    import litellm
    import numpy as np

    from eol_genai_service.resolution.embeddings import LiteLLMEmbedder
    from eol_genai_service.resolution.predicate_index import (
        EmbeddingPredicateResolver,
        PredicateEmbeddingIndex,
    )
    from eol_genai_service.resolution.predicates import PredicateTerm

    def boom(model, input, **kwargs):
        raise ConnectionError("embedding backend down")

    monkeypatch.setattr(litellm, "embedding", boom)
    index = PredicateEmbeddingIndex(
        [PredicateTerm(uri="VT_1", name="body mass", type="measurement", aliases=())],
        np.zeros((1, 4), dtype="float32"),
    )
    resolver = EmbeddingPredicateResolver(index, LiteLLMEmbedder("ollama/mxbai-embed-large"))
    deps = replace(build_offline_deps(), predicate_resolver=resolver)
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    assert result.outcome == "upstream_unavailable"
    assert "embedding" in result.detail.lower()


def test_upstream_unavailable_is_distinct_from_no_records():
    unavailable = answer(
        AnswerRequest(question="how heavy is a sea otter?"),
        _deps_with(lambda q, fmt: (_ for _ in ()).throw(TimeoutError("down"))),
    )
    no_records = answer(AnswerRequest(question="how heavy is a raccoon?"), build_offline_deps())
    assert unavailable.outcome == "upstream_unavailable"
    assert no_records.outcome == "no_records"
    assert unavailable.outcome != no_records.outcome
