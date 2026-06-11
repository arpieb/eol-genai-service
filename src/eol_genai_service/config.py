"""Service configuration (T005).

Settings the service needs to talk to EOL, choose models, and bound its behavior. Values are
read from the environment with deliberate defaults. Secrets (the EOL JWT) are never logged.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


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

    # Models (Principle IV — configurable, non-load-bearing). See research.md R2/R3.
    service_model_id: str = "claude-sonnet-4-6"
    embeddings_model_id: str = "voyage-3-large"

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
            service_model_id=os.getenv(
                "EOL_SERVICE_MODEL_ID", cls.model_fields["service_model_id"].default
            ),
            embeddings_model_id=os.getenv(
                "EOL_EMBEDDINGS_MODEL_ID", cls.model_fields["embeddings_model_id"].default
            ),
        )
