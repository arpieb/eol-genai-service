"""The ``categorical_attribute`` query shape (T030) — versioned template (Principle III).

Builds a read-only Cypher query for a categorical attribute (US-2, e.g. habitat). Reads the
``object_term`` value slot — the correct slot for a categorical predicate (FR-005) — and returns
the controlled value term with provenance. Mandatory ``LIMIT``; the predicate URI is the only
URI literal (case-sensitive).
"""

from __future__ import annotations

VERSION = "1.0.0"


def build_categorical_query(page_id: int, predicate_uri: str, cap: int) -> str:
    return (
        "MATCH (p:Page)-[:trait|inferred_trait]->(t:Trait)"
        f"-[:predicate]->(:Term {{uri:'{predicate_uri}'}}) "
        f"WHERE p.page_id = {int(page_id)} "
        "MATCH (t)-[:object_term]->(o:Term) "
        "OPTIONAL MATCH (t)-[:supplier]->(r:Resource) "
        "RETURN o.uri AS term_uri, o.name AS term_name, "
        "r.resource_id AS resource_id, r.name AS resource_name, t.citation AS citation "
        f"LIMIT {int(cap)}"
    )
