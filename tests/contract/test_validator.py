"""Validator contract tests (T018) — backs SC-002 and SC-003 hard gates.

Positive and negative coverage for each assertion: MISSING_LIMIT, UNRESOLVED_URI (case-sensitive),
NOT_READ_ONLY. See contracts/validator.md V2.
"""

from eol_genai_service.validator import validate

RESOLVED = {"VT_0001259", "RO_0002471"}


def _codes(query, resolved=RESOLVED):
    return {v.code for v in validate(query, resolved).violations}


def test_valid_query_passes():
    q = "MATCH (p:Page)-[:trait]->(t:Trait)-[:predicate]->(:Term {uri:'VT_0001259'}) RETURN p LIMIT 100"
    verdict = validate(q, RESOLVED)
    assert verdict.ok
    assert verdict.violations == ()


def test_missing_limit_is_rejected():
    q = "MATCH (p:Page)-[:predicate]->(:Term {uri:'VT_0001259'}) RETURN p"
    assert "MISSING_LIMIT" in _codes(q)


def test_limit_must_be_numeric():
    # A bare LIMIT keyword without a number does not satisfy the explicit-LIMIT requirement.
    q = "MATCH (p:Page) RETURN p LIMIT"
    assert "MISSING_LIMIT" in _codes(q)


def test_invented_uri_is_rejected():
    q = "MATCH (:Term {uri:'PATO_9999999'}) RETURN 1 LIMIT 10"
    assert "UNRESOLVED_URI" in _codes(q)


def test_uri_match_is_case_sensitive():
    q = "MATCH (:Term {uri:'VT_0001259'}) RETURN 1 LIMIT 10"
    # Exact-case resolved set → the URI is resolved, query passes.
    assert validate(q, {"VT_0001259"}).ok
    # Resolved set differs only by case → the uppercase URI is NOT a member (Principle II).
    assert "UNRESOLVED_URI" in {v.code for v in validate(q, {"vt_0001259"}).violations}
    # A different (still URI-shaped) URI that was never resolved is rejected.
    assert "UNRESOLVED_URI" in _codes("MATCH (:Term {uri:'VT_0001260'}) RETURN 1 LIMIT 10")


def test_write_clauses_are_rejected():
    for verb, snippet in [
        ("CREATE", "CREATE (n:Page) RETURN n LIMIT 1"),
        ("SET", "MATCH (p:Page) SET p.x = 1 RETURN p LIMIT 1"),
        ("DELETE", "MATCH (p:Page) DELETE p LIMIT 1"),
        ("MERGE", "MERGE (p:Page {id:1}) RETURN p LIMIT 1"),
        ("REMOVE", "MATCH (p:Page) REMOVE p.x RETURN p LIMIT 1"),
        ("DETACH", "MATCH (p:Page) DETACH DELETE p LIMIT 1"),
    ]:
        assert "NOT_READ_ONLY" in _codes(snippet), verb


def test_write_keyword_inside_string_literal_is_not_a_false_positive():
    # 'SET' appears only inside a quoted value, so the query is still read-only.
    q = "MATCH (t:Term {name:'asset SET CREATE'}) RETURN t LIMIT 5"
    assert "NOT_READ_ONLY" not in _codes(q)


def test_word_boundary_avoids_substring_false_positives():
    # 'ASSET' contains 'SET' but is not a write clause.
    q = "MATCH (p:Page) WHERE p.name = 'x' RETURN p.asset LIMIT 5"
    assert "NOT_READ_ONLY" not in _codes(q)


def test_multiple_violations_are_all_reported():
    q = "CREATE (:Term {uri:'PATO_9999999'}) RETURN 1"  # no LIMIT, invented URI, write
    codes = _codes(q)
    assert {"MISSING_LIMIT", "UNRESOLVED_URI", "NOT_READ_ONLY"} <= codes
