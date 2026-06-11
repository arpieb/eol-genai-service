"""US-5 lineage integration tests (T038), offline-fixture pipeline.

Independent test (spec): asking for a taxon's ancestry returns the lineage from the taxon up its
parent chain.
"""

from eol_genai_service.contract import AnswerRequest, ChosenSelection
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer
from eol_genai_service.shapes.lineage import build_lineage_query


def test_sea_otter_ancestry_returns_ordered_parent_chain():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what is the ancestry of the sea otter?"), deps)

    assert result.outcome == "answer"
    names = [s.value.taxon.scientific_name for s in result.statements]
    assert names == ["Enhydra", "Mustelidae", "Carnivora", "Mammalia"]  # immediate parent first
    first = result.statements[0]
    assert first.value.kind == "taxon"
    assert first.value.direction == "object_to_subject"  # ancestor → subject
    assert first.predicate.name == "parent taxon"


def test_lineage_query_has_limit_and_no_unresolved_uri():
    from eol_genai_service.validator import validate

    q = build_lineage_query(328583, 100)
    assert "LIMIT 100" in q
    assert validate(q, set()).ok  # no ontology URI literal; LIMIT present; read-only


def test_lineage_question_about_homonym_asks_for_clarification():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what is the lineage of an otter?"), deps)
    assert result.outcome == "needs_clarification"
    assert result.candidates.kind == "taxon"


def test_lineage_resubmit_with_chosen_taxon_answers():
    deps = build_offline_deps()
    result = answer(
        AnswerRequest(
            question="what is the lineage of an otter?",
            chosen=ChosenSelection(kind="taxon", page_id=328583),
        ),
        deps,
    )
    assert result.outcome == "answer"
    assert result.statements[0].subject.scientific_name == "Enhydra lutris"
