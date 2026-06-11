"""US-3 ecological-association integration tests (T032), offline-fixture pipeline.

Independent test (spec): "what do sea otters eat?" returns the partner taxa in the correct
direction (eater vs eaten) with provenance (FR-011).
"""

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer


def test_sea_otter_diet_returns_partner_taxon_in_correct_direction():
    deps = build_offline_deps()
    result = answer(AnswerRequest(question="what do sea otters eat?"), deps)

    assert result.outcome == "answer"
    stmt = result.statements[0]
    assert stmt.predicate.uri == "RO_0002470"  # eats
    assert stmt.value.kind == "taxon"
    # The partner is the EATEN taxon (subject otter → object urchin), never inverted (FR-011).
    assert stmt.value.taxon.scientific_name == "Strongylocentrotus"
    assert stmt.value.direction == "subject_to_object"
    assert stmt.provenance.resource["name"] == "GloBI"


def test_association_direction_helper():
    from eol_genai_service.shapes.association import association_direction

    assert association_direction("RO_0002470") == "subject_to_object"  # eats
    assert association_direction("RO_0002471") == "object_to_subject"  # eaten by
