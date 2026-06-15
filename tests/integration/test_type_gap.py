"""EOL type-gap integration: a measurement-typed predicate with categorical values (offline)."""

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer


def test_measurement_typed_predicate_with_categorical_value_answers_categorically():
    # "coloration" is typed `measurement` (as in EOL) but its value is an object_term. The
    # dual-slot attribute shape must return the categorical value, not no_records.
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what color is a raccoon?"), deps)
    assert result.outcome == "answer"
    stmt = result.statements[0]
    assert stmt.predicate.type == "measurement"  # EOL types it measurement...
    assert stmt.value.kind == "categorical"  # ...but the value is categorical (gap fixed)
    assert stmt.value.term.name == "brown"


def test_body_mass_still_quantitative_via_attribute_shape():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    assert result.outcome == "answer"
    assert result.statements[0].value.kind == "quantitative"
    assert result.statements[0].value.amount == 25.0


def test_habitat_still_categorical_via_attribute_shape():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what habitat does the raccoon live in?"), deps)
    assert result.outcome == "answer"
    assert result.statements[0].value.kind == "categorical"
    assert result.statements[0].value.term.name == "forest biome"
