"""The EOL upstream boundary — read-only, cached, capped, and gentle (Constitution Principle VII)."""

from eol_genai_service.upstream.client import (
    EolCypherClient,
    Transport,
    UpstreamResult,
    UpstreamUnavailable,
)
from eol_genai_service.upstream.run_cypher import ValidatorRejection, run_cypher

__all__ = [
    "EolCypherClient",
    "Transport",
    "UpstreamResult",
    "UpstreamUnavailable",
    "ValidatorRejection",
    "run_cypher",
]
