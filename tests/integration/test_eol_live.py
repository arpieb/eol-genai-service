"""Live EOL transport test (§2) — runs only when EOL_JWT is configured.

Hits the real ``https://eol.org/service/cypher`` endpoint to verify auth, execution, and
neo4j→row parsing against actual data. Skipped automatically in CI (no EOL_JWT), so CI stays
offline.
"""

import pytest

from eol_genai_service.config import Settings, load_env
from eol_genai_service.upstream.http_transport import HttpEolTransport

load_env()  # pick up a local .env so the skip condition sees EOL_JWT
_SETTINGS = Settings.from_env()

pytestmark = pytest.mark.skipif(not _SETTINGS.eol_jwt, reason="EOL_JWT not configured")


def test_live_query_returns_parsed_rows():
    transport = HttpEolTransport(_SETTINGS)
    rows = transport("MATCH (p:Page) RETURN p.page_id AS page_id LIMIT 1", "cypher")
    assert rows, "expected at least one row from EOL"
    assert "page_id" in rows[0]
    assert isinstance(rows[0]["page_id"], int)


def test_live_empty_result_is_an_empty_list():
    # A well-formed query that matches nothing → [] (no_records upstream), not an error.
    transport = HttpEolTransport(_SETTINGS)
    rows = transport(
        "MATCH (p:Page) WHERE p.page_id = -1 RETURN p.page_id AS page_id LIMIT 1", "cypher"
    )
    assert rows == []
