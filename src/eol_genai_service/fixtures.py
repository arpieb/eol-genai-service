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
    PredicateTerm(
        uri="ENVO_00000428",
        name="habitat",
        type="categorical",
        aliases=("habitat", "lives in", "live in", "where does", "biome", "environment"),
    ),
    PredicateTerm(
        uri="RO_0002470",
        name="eats",
        type="association",
        aliases=("eats", "eat", "what do", "what does", "preys on", "feeds on", "diet"),
    ),
    # A parent category: "body size" rolls up sub-types (body mass, body length) via the term
    # hierarchy (US-4 / FR-006). Distinct surface form ("body size") so it doesn't collide with
    # the bare "size" ambiguity exercised by US-6.
    PredicateTerm(
        uri="PATO_0000117",
        name="body size",
        type="measurement",
        aliases=("body size", "overall size", "size measurement"),
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
    # Partners in the US-7 diet chain (sea otter → urchin → kelp).
    TaxonRecord(page_id=598454, scientific_name="Strongylocentrotus", vernaculars=("sea urchin",)),
    TaxonRecord(page_id=699999, scientific_name="Macrocystis", vernaculars=("giant kelp",)),
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
    # US-2 categorical: raccoon habitat (object_term value rows).
    (328598, "ENVO_00000428"): [
        {
            "term_uri": "ENVO_01000174",
            "term_name": "forest biome",
            "resource_id": 7,
            "resource_name": "EOL Dynamic Hierarchy",
            "citation": None,
        }
    ],
    # US-3 association: sea otter eats sea urchin (object_page partner rows).
    (328583, "RO_0002470"): [
        {
            "partner_page_id": 598454,
            "partner_name": "Strongylocentrotus",
            "resource_id": 11,
            "resource_name": "GloBI",
            "citation": "Interaction record",
        }
    ],
}

# US-4: rolled-up counts keyed by the parent predicate URI. The roll-up itself lives in the
# Cypher template (the parent_term traversal); the fixture supplies the resulting total.
COUNT_ROWS: dict[str, list[dict[str, object]]] = {
    "PATO_0000117": [{"count": 3}],  # body size, rolled up over its sub-types
}

# US-5: ordered ancestor chain (immediate parent first) keyed by the taxon page_id.
LINEAGE_ROWS: dict[int, list[dict[str, object]]] = {
    328583: [
        {"ancestor_page_id": 328582, "ancestor_name": "Enhydra"},
        {"ancestor_page_id": 327332, "ancestor_name": "Mustelidae"},
        {"ancestor_page_id": 7662, "ancestor_name": "Carnivora"},
        {"ancestor_page_id": 1642, "ancestor_name": "Mammalia"},
    ],
}

# US-7: association edges for set-valued single_hop and n_hop_chain, keyed by predicate URI then
# source page_id → set of partner page_ids. The 2-hop diet chain: otter eats urchin eats kelp.
HOP_EDGES: dict[str, dict[int, set[int]]] = {
    "RO_0002470": {  # eats
        328583: {598454},  # sea otter → sea urchin
        598454: {699999},  # sea urchin → giant kelp
    },
}

_NAME_BY_PAGE: dict[int, str] = {r.page_id: r.scientific_name for r in TAXON_CATALOG}

_PAGE_RE = re.compile(r"page_id\s*=\s*(\d+)")
_URI_RE = re.compile(r"uri:'([A-Z][A-Z0-9]*_[0-9]+)'")


_IDS_RE = re.compile(r"page_id\s+IN\s+\[([\d,\s]*)\]")


def fixture_transport(query: str, fmt: str) -> list[dict[str, object]]:
    """Stand-in for the EOL network: dispatch on query shape and return canned rows."""
    uri_match = _URI_RE.search(query)
    page_match = _PAGE_RE.search(query)

    # US-7 n-hop chain: evaluate the ordered predicate chain over the hop edges (single LIMIT).
    if "with distinct" in query.lower():
        frontier = {int(page_match.group(1))} if page_match else set()
        for uri in _URI_RE.findall(query):  # in chain order
            edges = HOP_EDGES.get(uri, {})
            frontier = {p for src in frontier for p in edges.get(src, set())}
        return [
            {"result_page_id": p, "result_name": _NAME_BY_PAGE.get(p, "")} for p in sorted(frontier)
        ]

    # US-7 set-valued single hop: union the partners of every input page_id.
    ids_match = _IDS_RE.search(query)
    if ids_match and uri_match:
        ids = [int(x) for x in ids_match.group(1).split(",") if x.strip()]
        edges = HOP_EDGES.get(uri_match.group(1), {})
        partners = {p for src in ids for p in edges.get(src, set())}
        return [{"partner_page_id": p} for p in sorted(partners)]

    # Aggregate count (no page_id; counts across taxa) — keyed by the parent predicate URI.
    if "count(" in query.lower():
        return list(COUNT_ROWS.get(uri_match.group(1), [{"count": 0}])) if uri_match else []

    # Single-hop attribute/association: keyed by (page_id, predicate URI).
    if page_match and uri_match:
        return list(EOL_ROWS.get((int(page_match.group(1)), uri_match.group(1)), []))

    # Lineage: parent-chain traversal with a page_id and no ontology URI.
    if page_match and ":parent" in query:
        return list(LINEAGE_ROWS.get(int(page_match.group(1)), []))

    return []


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
    """Assemble a fully offline :class:`PipelineDeps` for the pipeline."""
    settings = settings or Settings()
    return PipelineDeps(
        extractor=RuleBasedExtractor(predicate_surface_forms(), taxon_surface_forms()),
        predicate_resolver=CatalogPredicateResolver(PREDICATE_CATALOG),
        taxon_resolver=CatalogTaxonResolver(TAXON_CATALOG),
        client=EolCypherClient(settings, fixture_transport),
        settings=settings,
    )


def build_offline_tool_surface(settings: Settings | None = None):
    """Assemble a fully offline :class:`ToolSurface` (US-7) over the fixture catalogs."""
    from eol_genai_service.contract import Predicate
    from eol_genai_service.tools.surface import DEFAULT_SCHEMA, ToolSurface

    deps = build_offline_deps(settings)
    predicates = [Predicate(uri=t.uri, name=t.name, type=t.type) for t in PREDICATE_CATALOG]
    return ToolSurface(deps, predicates, DEFAULT_SCHEMA)
