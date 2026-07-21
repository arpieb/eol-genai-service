"""Offline tests for the live EOL transport (§2): neo4j parsing + auth, via a mocked httpx client."""

import httpx
import pytest

from eol_genai_service.config import Settings
from eol_genai_service.upstream import UpstreamHttpError
from eol_genai_service.upstream.http_transport import HttpEolTransport, parse_neo4j_rows


def test_parse_neo4j_rows_columns_and_data():
    # The real recorded shape from the live endpoint.
    assert parse_neo4j_rows({"columns": ["page_id"], "data": [[58245907]]}) == [
        {"page_id": 58245907}
    ]
    multi = {
        "columns": ["uri", "name"],
        "data": [["http://purl.obolibrary.org/obo/VT_0001259", "body mass"], ["x", "y"]],
    }
    rows = parse_neo4j_rows(multi)
    assert rows[0] == {"uri": "http://purl.obolibrary.org/obo/VT_0001259", "name": "body mass"}
    assert len(rows) == 2
    assert parse_neo4j_rows({}) == []  # empty result is valid (no_records upstream)


def test_transport_attaches_jwt_header_and_parses():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"columns": ["page_id"], "data": [[42]]})

    mock = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HttpEolTransport(Settings(eol_jwt="secret-token"), client=mock)

    rows = transport("MATCH (p:Page) RETURN p.page_id AS page_id LIMIT 1", "cypher")
    assert rows == [{"page_id": 42}]
    assert seen["auth"] == "JWT secret-token"  # EOL's auth scheme (verified against live)
    assert seen["params"]["format"] == "cypher"
    assert "LIMIT 1" in seen["params"]["query"]


def test_transport_requires_a_jwt():
    with pytest.raises(ValueError):
        HttpEolTransport(Settings(eol_jwt=None))


def test_http_error_raises_upstream_http_error_with_status_and_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    mock = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HttpEolTransport(Settings(eol_jwt="x"), client=mock)
    # EolCypherClient wraps this into UpstreamUnavailable; the transport surfaces status + body.
    with pytest.raises(UpstreamHttpError) as exc_info:
        transport("RETURN 1 AS n LIMIT 1", "cypher")
    assert exc_info.value.status_code == 500
    assert "boom" in str(exc_info.value)


def test_403_body_is_surfaced_so_opaque_failures_are_debuggable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden: ORDER BY not permitted")

    mock = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HttpEolTransport(Settings(eol_jwt="x"), client=mock)
    with pytest.raises(UpstreamHttpError) as exc_info:
        transport("MATCH (p) RETURN p ORDER BY p LIMIT 1", "cypher")
    assert exc_info.value.status_code == 403
    assert exc_info.value.is_client_error
    assert "ORDER BY not permitted" in str(exc_info.value)


def test_error_body_is_truncated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="x" * 5000)

    mock = httpx.Client(transport=httpx.MockTransport(handler))
    transport = HttpEolTransport(Settings(eol_jwt="x"), client=mock)
    with pytest.raises(UpstreamHttpError) as exc_info:
        transport("RETURN 1 AS n LIMIT 1", "cypher")
    assert len(exc_info.value.body) == 500  # capped, not the full 5000-char body
