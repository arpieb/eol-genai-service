"""Contract-model conformance (supports T006; partial client-contract invariants).

Checks the tagged unions discriminate correctly and that the answer envelope always carries the
``truncated`` flag (invariant C2). Full end-to-end client-contract conformance (C1 no Cypher
leak across the live boundary) lands with the US-1 answer path.
"""

import json

from pydantic import TypeAdapter

from eol_genai_service.contract import (
    AnswerResult,
    NoRecordsResult,
    Predicate,
    QuantitativeValue,
    Result,
    Statement,
    Taxon,
    UpstreamUnavailableResult,
)

_result_adapter = TypeAdapter(Result)


def _sea_otter_mass_answer():
    return AnswerResult(
        statements=[
            Statement(
                subject=Taxon(page_id=328583, scientific_name="Enhydra lutris"),
                predicate=Predicate(uri="VT_0001259", name="body mass", type="measurement"),
                value=QuantitativeValue(amount=25.0, units="kg"),
            )
        ],
        cap=100,
    )


def test_answer_round_trips_and_keeps_truncated_flag():
    ans = _sea_otter_mass_answer()
    payload = json.loads(ans.model_dump_json())
    assert payload["outcome"] == "answer"
    assert payload["truncated"] is False  # always present (C2 / SC-005)
    assert payload["statements"][0]["value"]["kind"] == "quantitative"
    assert payload["statements"][0]["value"]["units"] == "kg"


def test_result_union_discriminates_by_outcome():
    for model in (
        _sea_otter_mass_answer(),
        NoRecordsResult(),
        UpstreamUnavailableResult(detail="timeout"),
    ):
        reparsed = _result_adapter.validate_json(model.model_dump_json())
        assert reparsed.outcome == model.outcome


def test_no_records_distinct_from_upstream_unavailable():
    # C8: these outcomes are never collapsed into one another.
    assert NoRecordsResult().outcome != UpstreamUnavailableResult(detail="x").outcome


def test_contract_payload_carries_no_cypher_or_neo4j_labels():
    # C1 (model-level): a serialized answer exposes none of the upstream's query/schema shape.
    blob = _sea_otter_mass_answer().model_dump_json().lower()
    for forbidden in ("cypher", "match (", "neo4j", "object_term", "normal_measurement"):
        assert forbidden not in blob
