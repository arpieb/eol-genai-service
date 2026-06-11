"""The ``lineage`` query shape (T039) — versioned template (Principle III).

Walks a taxon's parent chain (US-5) and returns the ordered ancestors. No ontology URI is
involved (it is a graph traversal over ``:parent``), so the validator sees no URIs to resolve;
the mandatory ``LIMIT`` and read-only assertions still apply.
"""

from __future__ import annotations

VERSION = "1.0.0"


def build_lineage_query(page_id: int, cap: int) -> str:
    return (
        "MATCH (p:Page)-[:parent*1..]->(ancestor:Page) "
        f"WHERE p.page_id = {int(page_id)} "
        "RETURN ancestor.page_id AS ancestor_page_id, "
        "ancestor.scientific_name AS ancestor_name "
        f"LIMIT {int(cap)}"
    )
