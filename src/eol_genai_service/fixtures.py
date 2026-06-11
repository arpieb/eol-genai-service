"""Offline fixtures for the US-1 answer path — NOT for production.

Provides a tiny in-memory EOL stand-in (term catalog, taxon catalog, and canned measurement rows)
plus a fixture transport that parses ``page_id`` + ``uri`` out of a validated Cypher query and
returns the matching rows. This lets the full pipeline run end-to-end with no network, JWT, LLM, or
embeddings. The live composition root swaps these for the embedded catalog, real resolvers, and an
httpx transport; nothing in the pipeline changes.
"""

from __future__ import annotations

import re

from eol_genai_service.config import Settings
from eol_genai_service.extraction.extract import RuleBasedExtractor
from eol_genai_service.orchestration.pipeline import PipelineDeps
from eol_genai_service.resolution.predicates import CatalogPredicateResolver, PredicateTerm
from eol_genai_service.resolution.taxa import CatalogTaxonResolver, TaxonRecord
from eol_genai_service.upstream.client import EolCypherClient

# --- Catalogs ---------------------------------------------------------------------------------

PREDICATE_CATALOG: list[PredicateTerm] = [
    PredicateTerm(
        uri="VT_0001259",
        name="body mass",
        type="measurement",
        # "size" is deliberately shared with body length below: a generic "size" question is
        # ambiguous between sub-types (US-6 / FR-006), so it must disambiguate, not guess.
        aliases=("body mass", "mass", "weight", "how heavy", "heavy", "weigh", "size"),
    ),
    PredicateTerm(
        uri="PATO_0000122",
        name="body length",
        type="measurement",
        aliases=("body length", "length", "long", "size"),
    ),
]

TAXON_CATALOG: list[TaxonRecord] = [
    # "otter" is a shared vernacular across two taxa — a homonym that must disambiguate (US-6).
    TaxonRecord(
        page_id=328583, scientific_name="Enhydra lutris", vernaculars=("sea otter", "otter")
    ),
    TaxonRecord(
        page_id=328587, scientific_name="Lontra canadensis", vernaculars=("river otter", "otter")
    ),
    # A taxon EOL describes but with no recorded body mass — exercises the no_records path.
    TaxonRecord(page_id=328598, scientific_name="Procyon lotor", vernaculars=("raccoon",)),
]

# Canned EOL measurement rows keyed by (page_id, predicate_uri). Absence → empty → no_records.
EOL_ROWS: dict[tuple[int, str], list[dict[str, object]]] = {
    (328583, "VT_0001259"): [
        {
            "amount": 25.0,
            "units": "kg",
            "resource_id": 42,
            "resource_name": "PanTHERIA",
            "citation": "Jones et al. 2009",
        }
    ],
    (328587, "VT_0001259"): [
        {
            "amount": 9.0,
            "units": "kg",
            "resource_id": 42,
            "resource_name": "PanTHERIA",
            "citation": "Jones et al. 2009",
        }
    ],
}

_PAGE_RE = re.compile(r"page_id\s*=\s*(\d+)")
_URI_RE = re.compile(r"uri:'([A-Z][A-Z0-9]*_[0-9]+)'")


def fixture_transport(query: str, fmt: str) -> list[dict[str, object]]:
    """Stand-in for the EOL network: resolve (page_id, uri) from the query and return rows."""
    page_match = _PAGE_RE.search(query)
    uri_match = _URI_RE.search(query)
    if not page_match or not uri_match:
        return []
    key = (int(page_match.group(1)), uri_match.group(1))
    return list(EOL_ROWS.get(key, []))


def predicate_surface_forms() -> set[str]:
    """Recognizable predicate surface phrases (lowercased), for the offline extractor."""
    forms: set[str] = set()
    for term in PREDICATE_CATALOG:
        forms.add(term.name.lower())
        forms.update(a.lower() for a in term.aliases)
    return forms


def taxon_surface_forms() -> set[str]:
    """Recognizable taxon surface phrases (lowercased), for the offline extractor."""
    forms: set[str] = set()
    for rec in TAXON_CATALOG:
        forms.add(rec.scientific_name.lower())
        forms.update(v.lower() for v in rec.vernaculars)
    return forms


def build_offline_deps(settings: Settings | None = None) -> PipelineDeps:
    """Assemble a fully offline :class:`PipelineDeps` for the US-1 pipeline."""
    settings = settings or Settings()
    return PipelineDeps(
        extractor=RuleBasedExtractor(predicate_surface_forms(), taxon_surface_forms()),
        predicate_resolver=CatalogPredicateResolver(PREDICATE_CATALOG),
        taxon_resolver=CatalogTaxonResolver(TAXON_CATALOG),
        client=EolCypherClient(settings, fixture_transport),
        settings=settings,
    )
