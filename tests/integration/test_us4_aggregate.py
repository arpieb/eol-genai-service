"""US-4 aggregate/count integration tests (T035), offline-fixture pipeline.

Independent test (spec): "how many taxa have a recorded body size?" returns a count that rolls up
sub-types of size (wingspan, body mass, ...) — FR-006.
"""

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer
from eol_genai_service.shapes.aggregate_count import build_aggregate_count_query


def test_body_size_count_is_rolled_up():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="how many taxa have a recorded body size?"), deps)
    assert result.outcome == "answer"
    assert result.count == 3  # rolled-up total across size sub-types
    assert result.statements == []  # a count answer carries no per-taxon statements


def test_aggregate_query_includes_rollup_traversal():
    # FR-006 roll-up is guaranteed by the template, not the data.
    q = build_aggregate_count_query("PATO_0000117", 1)
    assert "parent_term|synonym_of*0.." in q
    assert "count(" in q.lower()
    assert "LIMIT 1" in q


def test_aggregate_query_passes_validator():
    from eol_genai_service.validator import validate

    q = build_aggregate_count_query("PATO_0000117", 1)
    verdict = validate(q, {"PATO_0000117"})
    assert verdict.ok, verdict.violations


def test_zero_count_is_an_answer_not_no_records():
    # An unmodeled-but-resolvable count with no rows returns count 0, still an answer.
    deps = build_offline_deps()
    # "how many taxa eat?" resolves to the eats predicate (no COUNT_ROWS entry) → count 0.
    result = answer(AnswerRequest(question="how many taxa eat?"), deps)
    assert result.outcome == "answer"
    assert result.count == 0
