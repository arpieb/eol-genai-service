"""run_cypher no-bypass tests (T018 / contracts/validator.md V1).

Proves the validator is on the only path to EOL: on any violation, the upstream client is never
called and a ValidatorRejection is raised; on a valid query, the client is called exactly once.
This is the structural guarantee behind SC-002 and SC-003.
"""

import pytest

from eol_genai_service.upstream import (
    EolCypherClient,
    UpstreamResult,
    ValidatorRejection,
    run_cypher,
)
from eol_genai_service.config import Settings


class SpyClient(EolCypherClient):
    """Records whether fetch() was reached, without touching the network."""

    def __init__(self):
        self.calls = 0

    def fetch(self, query):  # type: ignore[override]
        self.calls += 1
        return UpstreamResult(rows=[{"p": 1}], truncated=False)


RESOLVED = {"VT_0001259"}


def test_valid_query_reaches_client_once():
    client = SpyClient()
    result = run_cypher("MATCH (:Term {uri:'VT_0001259'}) RETURN 1 LIMIT 10", RESOLVED, client)
    assert client.calls == 1
    assert result.rows == [{"p": 1}]


@pytest.mark.parametrize(
    "query",
    [
        "MATCH (:Term {uri:'VT_0001259'}) RETURN 1",  # MISSING_LIMIT
        "MATCH (:Term {uri:'PATO_9999999'}) RETURN 1 LIMIT 10",  # UNRESOLVED_URI
        "CREATE (n:Page) RETURN n LIMIT 1",  # NOT_READ_ONLY
    ],
)
def test_violation_blocks_upstream_call(query):
    client = SpyClient()
    with pytest.raises(ValidatorRejection):
        run_cypher(query, RESOLVED, client)
    assert client.calls == 0  # zero upstream calls on a rejected query


def test_settings_construct_from_env_without_secret(monkeypatch):
    monkeypatch.delenv("EOL_JWT", raising=False)
    settings = Settings.from_env()
    assert settings.eol_jwt is None
    assert settings.result_cap >= 1  # deliberate cap, never unbounded
