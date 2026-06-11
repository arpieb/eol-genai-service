"""US-2 categorical-attribute integration tests (T029), offline-fixture pipeline.

Independent test (spec): "what habitat does the raccoon live in?" returns the categorical habitat
value(s) and provenance.
"""

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer


def test_raccoon_habitat_returns_categorical_value_with_provenance():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what habitat does the raccoon live in?"), deps)

    assert result.outcome == "answer"
    stmt = result.statements[0]
    assert stmt.predicate.uri == "ENVO_00000428"
    assert stmt.predicate.type == "categorical"
    assert stmt.value.kind == "categorical"  # presented as a controlled term, not a measurement
    assert stmt.value.term.name == "forest biome"
    assert stmt.provenance.resource["name"] == "EOL Dynamic Hierarchy"


def test_categorical_answer_does_not_leak_neo4j_slot_names():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what habitat does the raccoon live in?"), deps)
    blob = result.model_dump_json().lower()
    for forbidden in ("object_term", "cypher", "match (", ":trait"):
        assert forbidden not in blob
