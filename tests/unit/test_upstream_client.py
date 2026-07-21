"""EOL client unit tests (T008) — caps, truncation flag, empty-vs-unavailable, bounded retry."""

import pytest

from eol_genai_service.config import Settings
from eol_genai_service.upstream import EolCypherClient, UpstreamHttpError, UpstreamUnavailable


def _client(transport, **overrides):
    settings = Settings(
        result_cap=overrides.pop("result_cap", 3),
        upstream_max_retries=overrides.pop("upstream_max_retries", 2),
        **overrides,
    )
    return EolCypherClient(settings, transport)


def test_empty_rows_are_a_valid_result_not_an_error():
    client = _client(lambda q, fmt: [])
    result = client.fetch("MATCH (p) RETURN p LIMIT 10")
    assert result.rows == []
    assert result.truncated is False


def test_result_cap_truncates_and_flags():
    rows = [{"i": i} for i in range(10)]
    client = _client(lambda q, fmt: rows, result_cap=3)
    result = client.fetch("MATCH (p) RETURN p LIMIT 10")
    assert len(result.rows) == 3
    assert result.truncated is True


def test_under_cap_is_not_flagged():
    client = _client(lambda q, fmt: [{"i": 0}], result_cap=3)
    assert client.fetch("MATCH (p) RETURN p LIMIT 10").truncated is False


def test_transport_failure_maps_to_upstream_unavailable_after_bounded_retry():
    attempts = {"n": 0}

    def failing(q, fmt):
        attempts["n"] += 1
        raise TimeoutError("eol timed out")

    client = _client(failing, upstream_max_retries=2)
    with pytest.raises(UpstreamUnavailable):
        client.fetch("MATCH (p) RETURN p LIMIT 10")
    assert attempts["n"] == 3  # initial + 2 retries (bounded, not a tight loop)


def test_client_error_fails_fast_without_retry_and_surfaces_body():
    attempts = {"n": 0}

    def forbidden(q, fmt):
        attempts["n"] += 1
        raise UpstreamHttpError(403, "Forbidden", "ORDER BY not permitted")

    client = _client(forbidden, upstream_max_retries=2)
    with pytest.raises(UpstreamUnavailable) as exc_info:
        client.fetch("MATCH (p) RETURN p LIMIT 10")
    assert attempts["n"] == 1  # 4xx is deterministic — no wasteful retry
    assert "403" in str(exc_info.value)
    assert "ORDER BY not permitted" in str(exc_info.value)  # body surfaced for debuggability


def test_server_error_is_retried_then_mapped_to_unavailable():
    attempts = {"n": 0}

    def flaky(q, fmt):
        attempts["n"] += 1
        raise UpstreamHttpError(503, "Service Unavailable", "try later")

    client = _client(flaky, upstream_max_retries=2)
    with pytest.raises(UpstreamUnavailable) as exc_info:
        client.fetch("MATCH (p) RETURN p LIMIT 10")
    assert attempts["n"] == 3  # 5xx may be transient — bounded retry (initial + 2)
    assert "503" in str(exc_info.value)


def test_format_param_is_passed_through_to_transport():
    seen = {}

    def transport(q, fmt):
        seen["fmt"] = fmt
        return []

    client = _client(transport)
    client.fetch("MATCH (p) RETURN p LIMIT 10")
    assert seen["fmt"] == "cypher"
