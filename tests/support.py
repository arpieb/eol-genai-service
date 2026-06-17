"""Shared test helpers — consolidates duplication across the integration/unit suites.

Covers the recurring pieces: Cypher-query normalization (record + replay MUST agree), the Ollama
skip-guard, recorded-cassette loading/replay, the recorded search-API resolver, an offline
PipelineDeps factory, and the real EOL ontology URI constants used by the recorded tests.
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

import httpx

from eol_genai_service.config import Settings
from eol_genai_service.extraction.extract import RuleBasedExtractor
from eol_genai_service.fixtures import (
    PREDICATE_CATALOG,
    TAXON_CATALOG,
    predicate_surface_forms,
    taxon_surface_forms,
)
from eol_genai_service.orchestration.pipeline import PipelineDeps
from eol_genai_service.resolution.predicates import CatalogPredicateResolver
from eol_genai_service.resolution.taxa import CatalogTaxonResolver
from eol_genai_service.resolution.taxon_search import SearchApiTaxonResolver
from eol_genai_service.upstream.client import EolCypherClient

CASSETTES = Path(__file__).resolve().parent / "fixtures" / "eol_cassettes"

# Real EOL ontology URIs (full form, as EOL stores them) — used by the recorded tests/scripts.
BODY_MASS = "http://purl.obolibrary.org/obo/VT_0001259"
EATS = "http://purl.obolibrary.org/obo/RO_0002470"
HABITAT = "http://rs.tdwg.org/dwc/terms/habitat"

_OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"


def norm(query: str) -> str:
    """Whitespace-normalize a Cypher query for cassette keying (record and replay must agree)."""
    return re.sub(r"\s+", " ", query).strip()


def ollama_up() -> bool:
    """True if a local Ollama server is reachable (skip-guard for live tests)."""
    try:
        urllib.request.urlopen(_OLLAMA_TAGS_URL, timeout=2)
        return True
    except Exception:
        return False


def load_cassette(name: str) -> dict:
    """Load a recorded cassette JSON from tests/fixtures/eol_cassettes/."""
    import json

    return json.loads((CASSETTES / name).read_text())


def replay_transport(cassette: dict):
    """A (query, fmt) -> rows transport that replays recorded rows (KeyError if unrecorded)."""

    def _transport(query: str, fmt: str):
        return cassette[norm(query)]

    return _transport


def recorded_search_resolver(search_cassette: dict) -> SearchApiTaxonResolver:
    """A SearchApiTaxonResolver backed by recorded search-API responses (no network)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=search_cassette[request.url.params["q"].lower()])

    return SearchApiTaxonResolver(client=httpx.Client(transport=httpx.MockTransport(handler)))


def offline_deps(transport, **settings_overrides) -> PipelineDeps:
    """An offline PipelineDeps over the fixture catalogs with a caller-supplied EOL ``transport``
    (e.g. a failing or counting transport) and optional Settings overrides."""
    settings = Settings(**settings_overrides)
    return PipelineDeps(
        extractor=RuleBasedExtractor(predicate_surface_forms(), taxon_surface_forms()),
        predicate_resolver=CatalogPredicateResolver(PREDICATE_CATALOG),
        taxon_resolver=CatalogTaxonResolver(TAXON_CATALOG),
        client=EolCypherClient(settings, transport),
        settings=settings,
    )
