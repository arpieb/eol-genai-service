"""The ``aggregate_count`` query shape (T036) — versioned template (Principle III).

Counts taxa that have a recorded value for a predicate, rolling up the predicate's sub-types via
the term hierarchy ``-[:parent_term|synonym_of*0..]->`` (US-4 / FR-006). A generic "body size"
count therefore includes body mass, body length, etc. Mandatory ``LIMIT``; the parent predicate
URI is the only URI literal.
"""

from __future__ import annotations

VERSION = "1.0.0"

# The roll-up traversal — gathers a term plus all of its sub-types/synonyms (FR-006).
ROLLUP_TRAVERSAL = "-[:parent_term|synonym_of*0..]->"


def build_aggregate_count_query(predicate_uri: str, cap: int) -> str:
    return (
        f"MATCH (term:Term){ROLLUP_TRAVERSAL}(:Term {{uri:'{predicate_uri}'}}) "
        "MATCH (p:Page)-[:trait|inferred_trait]->(:Trait)-[:predicate]->(term) "
        "RETURN count(DISTINCT p) AS count "
        "LIMIT 1"
    )
