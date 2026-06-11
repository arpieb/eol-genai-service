"""``run_cypher`` — the only path to EOL, validator-gated (T010 — Constitution Principle II).

Every query (template-derived or LLM-generated) reaches EOL exclusively through this function.
It calls the single validator FIRST and executes only on a positive verdict. A non-positive
verdict raises :class:`ValidatorRejection` and the upstream client is never touched — proving
"no bypass" (SC-002 / SC-003; contracts/validator.md V1).
"""

from __future__ import annotations

from collections.abc import Iterable

from eol_genai_service.upstream.client import EolCypherClient, UpstreamResult
from eol_genai_service.validator import Verdict, validate


class ValidatorRejection(Exception):
    """Raised when a query fails validation; the upstream call is not attempted."""

    def __init__(self, verdict: Verdict) -> None:
        self.verdict = verdict
        codes = ", ".join(v.code for v in verdict.violations)
        super().__init__(f"query rejected by validator: {codes}")


def run_cypher(query: str, resolved_uris: Iterable[str], client: EolCypherClient) -> UpstreamResult:
    """Validate then execute. The validator is on the only path to ``client.fetch``."""
    verdict = validate(query, resolved_uris)
    if not verdict.ok:
        raise ValidatorRejection(verdict)
    return client.fetch(query)
