"""Record real EOL responses into tests/fixtures/eol_cassettes/ (live-integration §6).

Run locally with EOL_JWT set (via .env): ``uv run python scripts/record_eol_cassettes.py``.
Re-run when the shapes change so the recorded-fixture CI tests replay current real data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from eol_genai_service.config import Settings, load_env
from eol_genai_service.shapes.attribute import build_attribute_query
from eol_genai_service.upstream.http_transport import HttpEolTransport

_OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eol_cassettes"
_CAP = 5
_BODY_MASS = "http://purl.obolibrary.org/obo/VT_0001259"
_HABITAT = "http://rs.tdwg.org/dwc/terms/habitat"

# (page_id, predicate_uri) pairs to record — keep in sync with test_eol_recorded.py.
_TRANSPORT_CASES = [(328598, _BODY_MASS), (47098272, _HABITAT)]
_SEARCH_NAMES = ["Enhydra lutris", "sea otter"]


def _norm(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def main() -> None:
    load_env()
    settings = Settings.from_env().model_copy(update={"upstream_timeout_seconds": 60.0})
    if not settings.eol_jwt:
        raise SystemExit("EOL_JWT not set — cannot record. Set it in .env.")
    transport = HttpEolTransport(settings)

    _OUT.mkdir(parents=True, exist_ok=True)

    cassette: dict[str, list] = {}
    for page, uri in _TRANSPORT_CASES:
        query = build_attribute_query(page, uri, _CAP)
        cassette[_norm(query)] = transport(query, "cypher")
        print(f"recorded page {page}: {len(cassette[_norm(query)])} rows")
    (_OUT / "transport.json").write_text(json.dumps(cassette, indent=1))

    search: dict[str, dict] = {}
    for name in _SEARCH_NAMES:
        resp = httpx.get(
            "https://eol.org/api/search/1.0.json", params={"q": name, "page": 1}, timeout=40
        )
        search[name.lower()] = resp.json()
        print(f"recorded search '{name}': {len(resp.json().get('results', []))} results")
    (_OUT / "search.json").write_text(json.dumps(search, indent=1))


if __name__ == "__main__":
    main()
