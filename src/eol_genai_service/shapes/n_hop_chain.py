"""Set-valued single-hop and server-side n-hop chain shapes (T041 / T043 — Principle III).

These are the templates behind the tool surface the *calling model* uses to orchestrate the novel
long tail. Two guarantees matter (research.md R7):

- **Set cardinality** — the single-hop template takes a *set* of page_ids (``IN [...]``) and returns
  a set, so chaining never fans out into hundreds of single-entity calls.
- **Single LIMIT** — the n-hop chain joins server-side under one ``LIMIT`` (the EOL
  ``WITH DISTINCT … carry page forward … match next predicate`` skeleton), so intermediate sets are
  never silently truncated per hop in the application layer.

Direction is carried per hop and asserted, never inverted (FR-011).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

VERSION = "1.0.0"

VALID_DIRECTIONS = ("subject_to_object", "object_to_subject")


def build_set_hop_query(page_ids: Iterable[int], predicate_uri: str, cap: int) -> str:
    """One association hop over a *set* of input page_ids (set-in, set-out)."""
    ids = ", ".join(str(int(p)) for p in sorted(set(page_ids)))
    return (
        "MATCH (p:Page)-[:trait|inferred_trait]->(t:Trait)"
        f"-[:predicate]->(:Term {{uri:'{predicate_uri}'}}) "
        f"WHERE p.page_id IN [{ids}] "
        "MATCH (t)-[:object_page]->(partner:Page) "
        "RETURN DISTINCT partner.page_id AS partner_page_id "
        f"LIMIT {int(cap)}"
    )


def build_n_hop_chain_query(start_page_id: int, hops: Sequence[tuple[str, str]], cap: int) -> str:
    """Chain N association hops server-side under a single ``LIMIT``.

    ``hops`` is an ordered list of ``(predicate_uri, direction)``. Each hop carries the frontier
    forward with ``WITH DISTINCT`` so the join stays on the server.
    """
    parts = [f"MATCH (p0:Page) WHERE p0.page_id = {int(start_page_id)}"]
    prev = "p0"
    for i, (uri, direction) in enumerate(hops, start=1):
        if direction not in VALID_DIRECTIONS:
            raise ValueError(f"invalid hop direction: {direction!r}")
        cur = f"p{i}"
        parts.append(
            f"MATCH ({prev})-[:trait|inferred_trait]->(t{i}:Trait)"
            f"-[:predicate]->(:Term {{uri:'{uri}'}})"
        )
        parts.append(f"MATCH (t{i})-[:object_page]->({cur}:Page)")
        parts.append(f"WITH DISTINCT {cur}")
        prev = cur
    parts.append(
        f"RETURN DISTINCT {prev}.page_id AS result_page_id, {prev}.scientific_name AS result_name"
    )
    parts.append(f"LIMIT {int(cap)}")
    return " ".join(parts)
