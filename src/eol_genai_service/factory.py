"""Composition root — assemble PipelineDeps from configuration (§2 + T011).

When an EOL JWT is configured, wire the **live** stack: Mellea extractor (Granite/Ollama),
embedding predicate resolver (EOL-enumerated catalog embedded with Ollama, full URIs), EOL
search-API taxon resolver, and the httpx transport — with embedding-tuned confidence thresholds.
Otherwise fall back to the offline fixture build. This is the one place that decides live-vs-offline;
the pipeline, contract, and validator stay unchanged either way.

The embedded predicate catalog is built once (enumerate ~645 terms + embed) and persisted under
``.cache/predicate_index`` (git-ignored); subsequent starts load it. Delete that dir to rebuild
after a model or catalog change.
"""

from __future__ import annotations

import os
from pathlib import Path

from eol_genai_service.config import Settings, load_env
from eol_genai_service.extraction.mellea_extractor import MelleaExtractor
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import PipelineDeps
from eol_genai_service.resolution.embeddings import (
    QUERY_PREFIX,
    Embedder,
    FastEmbedEmbedder,
    LiteLLMEmbedder,
)
from eol_genai_service.resolution.predicate_index import (
    EmbeddingPredicateResolver,
    PredicateEmbeddingIndex,
    enumerate_predicate_terms,
)
from eol_genai_service.resolution.taxon_search import SearchApiTaxonResolver
from eol_genai_service.upstream.client import EolCypherClient
from eol_genai_service.upstream.http_transport import HttpEolTransport

_INDEX_DIR = Path(".cache/predicate_index")

# Embedding cosine scores top out ~0.6, so the live path uses lower gates than the offline
# exact-match defaults. Applied only when the operator hasn't overridden them via env.
_EMBEDDING_CONFIDENCE = 0.5
_EMBEDDING_MARGIN = 0.05

# Backend names that mean "run the embedding model in-process" (fastembed / ONNX, CPU) — no
# Ollama, no hosted API. This is the MCP server's default (see tools.server.build_live_surface).
_LOCAL_EMBEDDING_BACKENDS = frozenset({"local", "fastembed"})


def build_deps(settings: Settings | None = None) -> PipelineDeps:
    """Build the live stack when EOL_JWT is configured, else the offline fixture deps."""
    load_env()  # pick up a local .env so from_env() sees EOL_JWT etc.
    settings = settings or Settings.from_env()

    if not settings.eol_jwt:
        return build_offline_deps(settings)

    settings = _with_embedding_thresholds(settings)
    transport = HttpEolTransport(settings)
    embedder = build_embedder(settings)
    return PipelineDeps(
        extractor=MelleaExtractor(settings),
        predicate_resolver=_build_or_load_predicate_resolver(transport, embedder),
        taxon_resolver=SearchApiTaxonResolver(),
        client=EolCypherClient(settings, transport),
        settings=settings,
    )


def build_embedder(settings: Settings) -> Embedder:
    """The configured embedder, selected by ``embeddings_backend``.

    ``local``/``fastembed`` → an in-process fastembed model (no server, no network, no key); any
    other value → litellm with a ``<backend>/<model_id>`` model string, optionally pointed at
    ``embeddings_api_base`` (a non-localhost Ollama, a gateway, self-hosted vLLM — ``None`` leaves
    litellm's provider default in place). The asymmetric query prefix is model-specific (mxbai needs
    it; most others don't), so it's derived here and lives inside the embedder. Catalog and query
    embeddings share this one builder so they always use the same model (the index-consistency
    invariant).
    """
    model_id = settings.embeddings_model_id
    query_prefix = QUERY_PREFIX if "mxbai" in model_id.lower() else ""
    if settings.embeddings_backend in _LOCAL_EMBEDDING_BACKENDS:
        # Pin the weights cache so a build-time pre-download is reused at runtime (offline start).
        # No api_base here: the model runs in this process, so there is no endpoint to point at.
        cache_dir = os.getenv("EOL_EMBEDDINGS_CACHE_DIR") or None
        return FastEmbedEmbedder(model_id, query_prefix=query_prefix, cache_dir=cache_dir)
    return LiteLLMEmbedder(
        f"{settings.embeddings_backend}/{model_id}",
        query_prefix=query_prefix,
        api_base=settings.embeddings_api_base,
    )


def _build_or_load_predicate_resolver(transport, embedder) -> EmbeddingPredicateResolver:
    if (_INDEX_DIR / "matrix.npy").exists():
        index = PredicateEmbeddingIndex.load(_INDEX_DIR)
    else:
        index = PredicateEmbeddingIndex.build(enumerate_predicate_terms(transport), embedder)
        index.save(_INDEX_DIR)
    return EmbeddingPredicateResolver(index, embedder)


def _with_embedding_thresholds(settings: Settings) -> Settings:
    """Lower the resolution gates for embedding scores, unless overridden from the defaults."""
    fields = Settings.model_fields
    updates: dict[str, float] = {}
    if (
        settings.resolution_confidence_threshold
        == fields["resolution_confidence_threshold"].default
    ):
        updates["resolution_confidence_threshold"] = _EMBEDDING_CONFIDENCE
    if settings.resolution_ambiguity_margin == fields["resolution_ambiguity_margin"].default:
        updates["resolution_ambiguity_margin"] = _EMBEDDING_MARGIN
    return settings.model_copy(update=updates) if updates else settings
