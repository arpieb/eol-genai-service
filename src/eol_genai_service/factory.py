"""Composition root — assemble PipelineDeps from configuration (§2).

When an EOL JWT is configured, wire the live httpx transport; otherwise fall back to the offline
fixture build. This is the one place that decides live-vs-offline, so the pipeline, contract, and
validator stay unchanged either way.

Note (intermediate state): the live branch currently still uses the offline ``RuleBasedExtractor``
and the fixture-catalog resolvers. Those emit fixture page_ids/URIs that won't match real EOL data,
so live queries will mostly return ``no_records`` until T011 replaces the resolvers with the
EOL-enumerated embedded catalog (and the validator/shapes are aligned to EOL's full URIs). The
*transport* — auth, execution, neo4j→row parsing, error mapping — is real and verified.
"""

from __future__ import annotations

from eol_genai_service.config import Settings, load_env
from eol_genai_service.extraction.extract import RuleBasedExtractor
from eol_genai_service.fixtures import (
    PREDICATE_CATALOG,
    TAXON_CATALOG,
    build_offline_deps,
    predicate_surface_forms,
    taxon_surface_forms,
)
from eol_genai_service.orchestration.pipeline import PipelineDeps
from eol_genai_service.resolution.predicates import CatalogPredicateResolver
from eol_genai_service.resolution.taxa import CatalogTaxonResolver
from eol_genai_service.upstream.client import EolCypherClient
from eol_genai_service.upstream.http_transport import HttpEolTransport


def build_deps(settings: Settings | None = None) -> PipelineDeps:
    """Build live deps when EOL_JWT is configured, else the offline fixture deps."""
    load_env()  # pick up a local .env so from_env() sees EOL_JWT etc.
    settings = settings or Settings.from_env()

    if not settings.eol_jwt:
        return build_offline_deps(settings)

    transport = HttpEolTransport(settings)
    return PipelineDeps(
        extractor=RuleBasedExtractor(predicate_surface_forms(), taxon_surface_forms()),
        predicate_resolver=CatalogPredicateResolver(PREDICATE_CATALOG),
        taxon_resolver=CatalogTaxonResolver(TAXON_CATALOG),
        client=EolCypherClient(settings, transport),
        settings=settings,
    )
