"""US-6 disambiguation integration tests (T024) — SC-004 hard gate (100%).

Every labeled-ambiguous input MUST yield ``needs_clarification`` rather than a silent wrong answer
(FR-009). The stateless resubmit with ``chosen`` then proceeds to an answer (FR-014).
"""

from eol_genai_service.contract import AnswerRequest, ChosenSelection
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer

# Labeled ambiguity set: each input is genuinely ambiguous and must NOT be answered outright.
AMBIGUOUS = [
    ("how heavy is an otter?", "taxon"),  # common name → sea otter vs river otter
    ("what is the size of an otter?", "taxon"),  # taxon ambiguity resolved first
    ("what is the size of a sea otter?", "predicate"),  # size → body mass vs body length
]


def test_sc004_every_ambiguous_input_asks_rather_than_guesses():
    deps = build_offline_deps()
    asked = 0
    for question, _kind in AMBIGUOUS:
        result = answer(AnswerRequest(question=question), deps)
        assert result.outcome == "needs_clarification", question
        asked += 1
    assert asked == len(AMBIGUOUS)  # 100% — SC-004 hard gate


def test_taxon_homonym_returns_both_candidates():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="how heavy is an otter?"), deps)
    assert result.outcome == "needs_clarification"
    assert result.candidates.kind == "taxon"
    pages = {c.page_id for c in result.candidates.items}
    assert pages == {328583, 328587}  # sea otter and river otter


def test_predicate_ambiguity_returns_predicate_candidates():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what is the size of a sea otter?"), deps)
    assert result.outcome == "needs_clarification"
    assert result.candidates.kind == "predicate"
    uris = {c.uri for c in result.candidates.items}
    assert uris == {"VT_0001259", "PATO_0000122"}  # body mass and body length


def test_resubmit_with_chosen_taxon_proceeds_to_answer():
    deps = build_offline_deps()
    # First call asks; resubmit picks the sea otter explicitly (FR-014, stateless).
    result = answer(
        AnswerRequest(
            question="how heavy is an otter?",
            chosen=ChosenSelection(kind="taxon", page_id=328583),
        ),
        deps,
    )
    assert result.outcome == "answer"
    assert result.statements[0].subject.scientific_name == "Enhydra lutris"
    assert result.statements[0].value.amount == 25.0


def test_resubmit_with_other_chosen_taxon_answers_that_one():
    deps = build_offline_deps()
    result = answer(
        AnswerRequest(
            question="how heavy is an otter?",
            chosen=ChosenSelection(kind="taxon", page_id=328587),
        ),
        deps,
    )
    assert result.outcome == "answer"
    assert result.statements[0].subject.scientific_name == "Lontra canadensis"
    assert result.statements[0].value.amount == 9.0


def test_unambiguous_question_still_answers_directly():
    # Regression: a confident single-fact question is unaffected by the homonym fixtures.
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    assert result.outcome == "answer"
    assert result.statements[0].subject.scientific_name == "Enhydra lutris"
