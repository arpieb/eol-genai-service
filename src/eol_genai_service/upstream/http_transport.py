"""Live EOL Cypher transport over httpx (§2 — deferred half of T008).

The real upstream boundary: GET ``EOL_CYPHER_URL`` with ``query`` + ``format`` params and an
``Authorization: JWT <token>`` header, parsing neo4j's native ``{"columns": [...], "data": [[...]]}``
JSON into row dicts keyed by the RETURN aliases — the shape the mappers expect (Constitution
Principle I; the neo4j envelope never escapes this module).

Verified against the live endpoint: auth header `JWT <token>`, response
``{"columns": ["page_id"], "data": [[58245907]]}``. On a non-2xx response the transport raises
:class:`UpstreamHttpError` carrying the status + response body (so failures like EOL's 403 stay
debuggable); ``EolCypherClient`` wraps that into ``UpstreamUnavailable`` (FR-013), failing fast on
4xx and applying bounded retry on 5xx/transport errors.
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from eol_genai_service.config import Settings
from eol_genai_service.upstream.client import UpstreamHttpError

# EOL's error bodies are short (a line or two); cap what we surface so a stray HTML page can't
# flood logs or the caller's context.
_MAX_ERROR_BODY_CHARS = 500


def parse_neo4j_rows(payload: dict) -> list[dict[str, object]]:
    """Turn neo4j ``{columns, data}`` JSON into a list of column-keyed row dicts."""
    columns: Sequence[str] = payload.get("columns", []) or []
    data: Sequence[Sequence[object]] = payload.get("data", []) or []
    return [dict(zip(columns, row, strict=False)) for row in data]


class HttpEolTransport:
    """Callable ``(query, fmt) -> rows`` that executes Cypher against the live EOL endpoint.

    Holds a reusable httpx client. The shared admin JWT is attached per request and never logged.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.eol_jwt:
            raise ValueError("HttpEolTransport requires settings.eol_jwt to be set")
        self._url = settings.eol_cypher_url
        self._jwt = settings.eol_jwt
        self._client = client or httpx.Client(timeout=settings.upstream_timeout_seconds)

    def __call__(self, query: str, fmt: str) -> list[dict[str, object]]:
        resp = self._client.get(
            self._url,
            params={"query": query, "format": fmt},
            headers={"Authorization": f"JWT {self._jwt}"},
        )
        if (
            resp.is_error
        ):  # non-2xx: surface status + body so opaque failures (e.g. 403) are debuggable
            body = (resp.text or "")[:_MAX_ERROR_BODY_CHARS]
            raise UpstreamHttpError(resp.status_code, resp.reason_phrase, body)
        return parse_neo4j_rows(resp.json())
