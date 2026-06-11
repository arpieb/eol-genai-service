"""The ``single_fact`` query shape (T021) — a versioned, deterministic template (Principle III).

Builds a read-only Cypher query for "one measurable attribute of one taxon" (US-1). The query
carries a mandatory ``LIMIT`` and references only the resolved predicate URI, so it clears the
validator. The ``uri`` is interpolated as a case-sensitive string literal (EOL URIs are uppercase).
"""

from __future__ import annotations

VERSION = "1.0.0"


def build_single_fact_query(page_id: int, predicate_uri: str, cap: int) -> str:
    """Return Cypher fetching a taxon's measurement(s) for one predicate, with provenance.

    ``page_id`` and ``cap`` are integers (no injection surface); ``predicate_uri`` is a resolved,
    validator-checked URI. Maps the EOL statement pattern
    ``(:Page)-[:trait|inferred_trait]->(:Trait)-[:predicate]->(:Term)`` to a measurement row.
    """
    return (
        "MATCH (p:Page)-[:trait|inferred_trait]->(t:Trait)"
        f"-[:predicate]->(:Term {{uri:'{predicate_uri}'}}) "
        f"WHERE p.page_id = {int(page_id)} "
        "OPTIONAL MATCH (t)-[:supplier]->(r:Resource) "
        "RETURN t.normal_measurement AS amount, t.normal_units AS units, "
        "r.resource_id AS resource_id, r.name AS resource_name, t.citation AS citation "
        f"LIMIT {int(cap)}"
    )
