"""The ``association`` query shape (T033) — versioned template (Principle III).

Builds a read-only Cypher query for an ecological association (US-3, e.g. "what do sea otters
eat?"). Reads the ``object_page`` value slot — the correct slot for an association predicate
(FR-005) — returning the partner taxon with provenance. Direction is significant and asserted
(FR-011): ``RO_0002470`` ("eats") points subject→object (eater→eaten); ``RO_0002471`` ("eaten
by") is the inverse. Mandatory ``LIMIT``; the predicate URI is the only URI literal.
"""

from __future__ import annotations

VERSION = "1.0.0"

# Direction the partner sits in, by predicate URI. subject_to_object = the partner is the object
# (e.g. for "eats", the partner is the eaten taxon).
_DIRECTION_BY_URI: dict[str, str] = {
    "RO_0002470": "subject_to_object",  # eats
    "RO_0002471": "object_to_subject",  # eaten by
}


def association_direction(predicate_uri: str) -> str:
    """Return the asserted relationship direction for an association predicate."""
    return _DIRECTION_BY_URI.get(predicate_uri, "subject_to_object")


def build_association_query(page_id: int, predicate_uri: str, cap: int) -> str:
    return (
        "MATCH (p:Page)-[:trait|inferred_trait]->(t:Trait)"
        f"-[:predicate]->(:Term {{uri:'{predicate_uri}'}}) "
        f"WHERE p.page_id = {int(page_id)} "
        "MATCH (t)-[:object_page]->(partner:Page) "
        "OPTIONAL MATCH (t)-[:supplier]->(r:Resource) "
        "RETURN partner.page_id AS partner_page_id, partner.scientific_name AS partner_name, "
        "r.resource_id AS resource_id, r.name AS resource_name, t.citation AS citation "
        f"LIMIT {int(cap)}"
    )
