"""Taxon resolution via EOL's public search API (T011 — FR-003).

EOL's Cypher ``Page`` nodes carry only ``page_id`` — scientific names aren't there — so taxon
name→id resolution uses EOL's public search API (``/api/search``), which returns ranked
``{id, title}`` candidates for both scientific and common names. This is the "prefer EOL's own
page/search lookup" path (FR-003) and feeds US-6 disambiguation directly.

Scoring (informed by probing): an **exact title match** is confident (1.0); otherwise candidates
score below the confidence threshold so ambiguous names (e.g. "sea otter", whose search surfaces
several virus pages above the species) yield ``needs_clarification`` rather than a confident wrong
pick. The candidate list is the real set the user chooses from.
"""

from __future__ import annotations

import httpx

from eol_genai_service.contract import Taxon, TaxonCandidate
from eol_genai_service.upstream.client import UpstreamUnavailable

SEARCH_URL = "https://eol.org/api/search/1.0.json"


class SearchApiTaxonResolver:
    """Resolve taxon names to EOL page ids via the public search API."""

    def __init__(self, client: httpx.Client | None = None, k: int = 5) -> None:
        self._client = client or httpx.Client(timeout=20.0)
        self._k = k

    def resolve(self, name: str) -> list[TaxonCandidate]:
        # The search API is an upstream dependency: map its transport / rate-limit (429) / 5xx
        # failures to the shared ``UpstreamUnavailable`` signal so httpx never leaks through the
        # TaxonResolver protocol and the pipeline surfaces ``upstream_unavailable`` (like the EOL
        # Cypher path), not an unhandled crash.
        try:
            resp = self._client.get(SEARCH_URL, params={"q": name, "page": 1})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable(f"taxon search unavailable: {exc}") from exc
        results = resp.json().get("results", [])[: self._k]

        needle = name.strip().lower()
        candidates: list[TaxonCandidate] = []
        for i, r in enumerate(results):
            title = str(r.get("title", ""))
            exact = title.strip().lower() == needle
            score = 1.0 if exact else max(0.0, 0.45 - 0.03 * i)  # non-exact stays below threshold
            candidates.append(
                TaxonCandidate(page_id=int(r["id"]), scientific_name=title, score=score)
            )
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def by_page_id(self, page_id: int) -> Taxon | None:
        # The search API has no reverse lookup; the chosen-resubmit (FR-014) only needs the page_id
        # for the query. Name enrichment via the EOL pages API is a follow-up.
        return Taxon(page_id=page_id, scientific_name=f"page:{page_id}")
