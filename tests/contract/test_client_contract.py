"""Client-contract conformance for the US-1 answer path (T020).

Checks invariants C1–C5 against the JSON the boundary actually emits: no Cypher/neo4j leak (C1),
truncated always present (C2), provenance present (C3), correct value slot (C4), and (for taxon
values, exercised later) direction. Driven through the offline pipeline.
"""

import json

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer


def _answer_payload():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    return json.loads(result.model_dump_json())


def test_c1_no_cypher_or_neo4j_shape_on_the_boundary():
    blob = json.dumps(_answer_payload()).lower()
    for forbidden in ("cypher", "match (", "neo4j", ":trait", "normal_measurement", "object_term"):
        assert forbidden not in blob, forbidden


def test_c2_truncated_flag_always_present():
    assert "truncated" in _answer_payload()


def test_c3_provenance_present_on_statements():
    payload = _answer_payload()
    assert payload["statements"][0]["provenance"]["resource"]["name"] == "PanTHERIA"


def test_c4_value_kind_matches_predicate_type():
    payload = _answer_payload()
    assert payload["statements"][0]["predicate"]["type"] == "measurement"
    assert payload["statements"][0]["value"]["kind"] == "quantitative"
