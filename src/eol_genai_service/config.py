"""Service configuration (T005).

Settings the service needs to talk to EOL, choose models, and bound its behavior. Values are
read from the environment with deliberate defaults. Secrets (the EOL JWT) are never logged.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


def load_env() -> None:
    """Load a local ``.env`` file into the process environment, if present.

    Called once at the application composition root (not in :meth:`Settings.from_env`, which stays
    a pure reader of the process environment so tests are deterministic). Real environment variables
    take precedence over ``.env`` (``override=False``); secrets live only in the git-ignored
    ``.env`` file, never in the committed ``.env.example``.
    """
    from dotenv import find_dotenv, load_dotenv

    # Search from the current working directory (where the operator runs the app), not the
    # package location, so the operator's .env is found regardless of install layout.
    load_dotenv(find_dotenv(usecwd=True), override=False)


class Settings(BaseModel):
    """Runtime configuration. Construct via :meth:`from_env`.

    The defaults encode the upstream-care constraints from Constitution Principle VII: a
    deliberate result cap and term-list cache TTL, never "unbounded".
    """

    # Upstream EOL Cypher endpoint
    eol_cypher_url: str = "https://eol.org/service/cypher"
    eol_jwt: str | None = Field(default=None, repr=False)  # secret: kept out of repr/logs
    eol_format: str = "cypher"  # native neo4j JSON; mapped, never passed through (Principle I)

    # Deliberate caps and caching (Principle VII)
    result_cap: int = 100
    term_cache_ttl_seconds: int = 24 * 60 * 60
    upstream_timeout_seconds: float = 10.0
    upstream_max_retries: int = 2  # bounded retry with backoff, never a tight loop (FR-013)

    # Models (configurable, non-load-bearing). See research.md R2/R3 and constitution v1.1.0.
    # The scoped service-side extractor (Principle V) defaults to Mellea's local Granite/Ollama
    # backend — no API key, offline, cheap. A frontier Claude model is a drop-in configurable
    # upgrade for the hard disambiguation/repair tail (set EOL_SERVICE_MODEL_BACKEND=anthropic
    # and EOL_SERVICE_MODEL_ID=claude-sonnet-4-6).
    service_model_backend: str = "ollama"  # "ollama" (local default) | "anthropic"
    service_model_id: str = "granite4.1:3b"
    # Embeddings (the term→URI grounding, Principle IV — load-bearing, so subject to a recall@k
    # bake-off before scale; see research R2). Default to a local Ollama model: no key, offline,
    # and off the hot path (every query embeds the user's phrase). Voyage is a configurable upgrade
    # (set EOL_EMBEDDINGS_BACKEND=voyage and EOL_EMBEDDINGS_MODEL_ID=voyage-3-large).
    # NOTE: catalog and query embeddings MUST use the same model — changing it requires an index
    # rebuild (CatalogIndex.rebuild()).
    embeddings_backend: str = "ollama"  # "ollama" (local default) | "voyage"
    embeddings_model_id: str = "mxbai-embed-large"

    # Resolution confidence gates. Defaults suit exact-match (offline) scores; the live embedding
    # path uses lower values (cosine tops out ~0.6), set by the composition root (see factory).
    resolution_confidence_threshold: float = 0.85
    resolution_ambiguity_margin: float = 0.15

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables, falling back to the defaults above."""

        def _int(name: str, default: int) -> int:
            raw = os.getenv(name)
            return int(raw) if raw is not None else default

        def _float(name: str, default: float) -> float:
            raw = os.getenv(name)
            return float(raw) if raw is not None else default

        return cls(
            eol_cypher_url=os.getenv("EOL_CYPHER_URL", cls.model_fields["eol_cypher_url"].default),
            eol_jwt=os.getenv("EOL_JWT"),
            eol_format=os.getenv("EOL_FORMAT", cls.model_fields["eol_format"].default),
            result_cap=_int("EOL_RESULT_CAP", cls.model_fields["result_cap"].default),
            term_cache_ttl_seconds=_int(
                "EOL_TERM_CACHE_TTL_SECONDS", cls.model_fields["term_cache_ttl_seconds"].default
            ),
            upstream_timeout_seconds=_float(
                "EOL_UPSTREAM_TIMEOUT_SECONDS",
                cls.model_fields["upstream_timeout_seconds"].default,
            ),
            upstream_max_retries=_int(
                "EOL_UPSTREAM_MAX_RETRIES", cls.model_fields["upstream_max_retries"].default
            ),
            service_model_backend=os.getenv(
                "EOL_SERVICE_MODEL_BACKEND", cls.model_fields["service_model_backend"].default
            ),
            service_model_id=os.getenv(
                "EOL_SERVICE_MODEL_ID", cls.model_fields["service_model_id"].default
            ),
            embeddings_backend=os.getenv(
                "EOL_EMBEDDINGS_BACKEND", cls.model_fields["embeddings_backend"].default
            ),
            embeddings_model_id=os.getenv(
                "EOL_EMBEDDINGS_MODEL_ID", cls.model_fields["embeddings_model_id"].default
            ),
            resolution_confidence_threshold=_float(
                "EOL_RESOLUTION_CONFIDENCE_THRESHOLD",
                cls.model_fields["resolution_confidence_threshold"].default,
            ),
            resolution_ambiguity_margin=_float(
                "EOL_RESOLUTION_AMBIGUITY_MARGIN",
                cls.model_fields["resolution_ambiguity_margin"].default,
            ),
        )
