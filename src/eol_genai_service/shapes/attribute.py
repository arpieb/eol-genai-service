"""The unified single-hop ``attribute`` shape (EOL type-gap fix — Principle III).

EOL types both numeric and categorical predicates as ``measurement`` (e.g. ``habitat`` is typed
``measurement`` though its values live in ``object_term``), so the predicate type alone can't tell
us which value slot to read. This shape reads **both** slots in one query — ``normal_measurement``
(a Trait property) and ``object_term`` (a Term relationship) — and the mapper emits a quantitative
or categorical value per row depending on which slot is populated (FR-005). It subsumes the
``single_fact`` and ``categorical_attribute`` shapes for live use. Mandatory ``LIMIT``; the
predicate URI is the only URI literal.
"""

from __future__ import annotations

VERSION = "1.0.0"


def build_attribute_query(page_id: int, predicate_uri: str, cap: int) -> str:
    return (
        "MATCH (p:Page)-[:trait|inferred_trait]->(t:Trait)"
        f"-[:predicate]->(:Term {{uri:'{predicate_uri}'}}) "
        f"WHERE p.page_id = {int(page_id)} "
        "OPTIONAL MATCH (t)-[:object_term]->(o:Term) "
        "OPTIONAL MATCH (t)-[:supplier]->(r:Resource) "
        "RETURN t.normal_measurement AS amount, t.normal_units AS units, "
        "o.uri AS term_uri, o.name AS term_name, "
        "r.resource_id AS resource_id, r.name AS resource_name, t.citation AS citation "
        f"LIMIT {int(cap)}"
    )
