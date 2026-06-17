"""Unit tests for the set-valued hop shapes — direction is honored, not just validated (FR-011/R7).

The bug these guard against: a query that ignores ``direction`` would silently serve
``subject_to_object`` results for an ``object_to_subject`` request — the exact direction-inversion
failure R7 warns about.
"""

import pytest

from eol_genai_service.shapes.n_hop_chain import (
    build_n_hop_chain_query,
    build_set_hop_query,
)
from eol_genai_service.validator import validate

_EATS = "http://purl.obolibrary.org/obo/RO_0002470"


def test_set_hop_subject_to_object_filters_subjects_returns_objects():
    q = build_set_hop_query({328583, 598454}, _EATS, 50, "subject_to_object")
    # Inputs are the subjects; the object partners come back.
    assert "WHERE p.page_id IN [328583, 598454]" in q
    assert "MATCH (t)-[:object_page]->(partner:Page)" in q
    assert "LIMIT 50" in q
    assert validate(q, {_EATS}).ok


def test_set_hop_object_to_subject_inverts_the_traversal():
    q = build_set_hop_query({699999}, _EATS, 50, "object_to_subject")
    # Inputs are now the objects; the filter sits on the object side and subjects come back.
    assert "MATCH (t)-[:object_page]->(o:Page) WHERE o.page_id IN [699999]" in q
    assert "WHERE p.page_id IN" not in q  # inputs are NOT treated as subjects
    assert "RETURN DISTINCT partner.page_id" in q
    assert validate(q, {_EATS}).ok


def test_set_hop_directions_produce_different_queries():
    fwd = build_set_hop_query({1, 2}, _EATS, 5, "subject_to_object")
    rev = build_set_hop_query({1, 2}, _EATS, 5, "object_to_subject")
    assert fwd != rev  # the whole point — direction changes the query, not just passes a check


def test_set_hop_rejects_invalid_direction():
    with pytest.raises(ValueError):
        build_set_hop_query({1}, _EATS, 5, "sideways")


def test_n_hop_chain_inverts_an_object_to_subject_hop():
    # Hop 1 forward, hop 2 inverted: the inverted hop matches the next frontier as the SUBJECT.
    q = build_n_hop_chain_query(
        328583, [(_EATS, "subject_to_object"), (_EATS, "object_to_subject")], 25
    )
    assert "MATCH (p0)-[:trait|inferred_trait]->(t1:Trait)" in q  # hop 1: frontier is subject
    assert "MATCH (t1)-[:object_page]->(p1:Page)" in q
    assert "MATCH (p2:Page)-[:trait|inferred_trait]->(t2:Trait)" in q  # hop 2: frontier is object
    assert "MATCH (t2)-[:object_page]->(p1)" in q  # ...points back to the prior frontier
    assert "LIMIT 25" in q


def test_n_hop_chain_rejects_invalid_direction():
    with pytest.raises(ValueError):
        build_n_hop_chain_query(1, [(_EATS, "sideways")], 5)
