"""SC-001 accuracy harness (T045): canonical-shape questions vs hand-written expectations.

The golden set covers US-1..US-5. Accuracy = correct / total must clear the SC-001 target (≥90%).
With the deterministic offline fixtures this is 100%; the harness is what makes the gate real and
will run against recorded EOL fixtures once live.
"""

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer

SC001_TARGET = 0.90


def _is_mass_answer(r):
    return r.outcome == "answer" and r.statements[0].value.amount == 25.0


def _is_no_records(r):
    return r.outcome == "no_records"


def _is_habitat(r):
    return r.outcome == "answer" and r.statements[0].value.term.name == "forest biome"


def _is_diet(r):
    return (
        r.outcome == "answer"
        and r.statements[0].value.taxon.scientific_name == "Strongylocentrotus"
        and r.statements[0].value.direction == "subject_to_object"
    )


def _is_count_3(r):
    return r.outcome == "answer" and r.count == 3


def _is_lineage(r):
    return r.outcome == "answer" and [s.value.taxon.scientific_name for s in r.statements] == [
        "Enhydra",
        "Mustelidae",
        "Carnivora",
        "Mammalia",
    ]


GOLDEN = [
    ("how heavy is a sea otter?", _is_mass_answer),  # US-1
    ("how heavy is a raccoon?", _is_no_records),  # US-1 (no data)
    ("what habitat does the raccoon live in?", _is_habitat),  # US-2
    ("what do sea otters eat?", _is_diet),  # US-3
    ("how many taxa have a recorded body size?", _is_count_3),  # US-4
    ("what is the ancestry of the sea otter?", _is_lineage),  # US-5
]


def test_canonical_accuracy_meets_sc001_target():
    deps = build_offline_deps()
    correct = sum(1 for q, check in GOLDEN if check(answer(AnswerRequest(question=q), deps)))
    accuracy = correct / len(GOLDEN)
    assert accuracy >= SC001_TARGET, f"accuracy {accuracy:.0%} < target {SC001_TARGET:.0%}"
