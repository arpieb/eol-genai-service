"""Offline tests for the EOL search-API taxon resolver (T011) — mocked httpx."""

import httpx
import pytest

from eol_genai_service.resolution.taxon_search import SearchApiTaxonResolver
from eol_genai_service.upstream.client import UpstreamUnavailable

# Recorded shapes from the live search API.
_RESPONSES = {
    "enhydra lutris": {
        "results": [
            {"id": 46559130, "title": "Enhydra lutris"},
            {"id": 1, "title": "Enhydra lutris lutris"},
        ]
    },
    "sea otter": {
        "results": [
            {"id": 55560047, "title": "Sea otter herpesvirus"},
            {"id": 51950753, "title": "Sea otter poxvirus"},
        ]
    },
}


def _resolver() -> SearchApiTaxonResolver:
    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"].lower()
        return httpx.Response(200, json=_RESPONSES.get(q, {"results": []}))

    return SearchApiTaxonResolver(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_exact_scientific_name_is_confident():
    cands = _resolver().resolve("Enhydra lutris")
    assert cands[0].page_id == 46559130
    assert cands[0].score == 1.0  # exact title match → confident


def test_ambiguous_common_name_scores_below_confidence():
    # "sea otter" surfaces viruses, no exact match → all candidates below the live threshold (0.5)
    # so the pipeline asks for clarification rather than confidently picking a virus.
    cands = _resolver().resolve("sea otter")
    assert cands
    assert all(c.score < 0.5 for c in cands)
    assert {c.page_id for c in cands} == {55560047, 51950753}


def test_by_page_id_returns_taxon_for_resubmit():
    taxon = _resolver().by_page_id(328598)
    assert taxon is not None
    assert taxon.page_id == 328598


def test_rate_limit_maps_to_upstream_unavailable():
    # A 429 (or any 5xx) from the search API surfaces as the shared upstream signal, not an httpx
    # error leaking through the resolver protocol.
    def rate_limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    resolver = SearchApiTaxonResolver(
        client=httpx.Client(transport=httpx.MockTransport(rate_limited))
    )
    with pytest.raises(UpstreamUnavailable):
        resolver.resolve("Enhydra lutris")


def test_transport_error_maps_to_upstream_unavailable():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("search api unreachable")

    resolver = SearchApiTaxonResolver(client=httpx.Client(transport=httpx.MockTransport(down)))
    with pytest.raises(UpstreamUnavailable):
        resolver.resolve("Enhydra lutris")
