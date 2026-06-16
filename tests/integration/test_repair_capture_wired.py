"""D1: the pipeline records out_of_capability outcomes as repair misses (research.md R8).

Capture is the live observability seam that grows the rule set from real gaps. It records *only*
genuine capability gaps — not no_records (a valid answer, Principle VII) and not needs_clarification
(healthy disambiguation).
"""

from dataclasses import replace

from eol_genai_service.contract import AnswerRequest, OutOfCapabilityResult
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer
from eol_genai_service.repair.capture import MissCapture


def _run_with_capture(question: str) -> tuple[object, MissCapture]:
    capture = MissCapture()
    deps = replace(build_offline_deps(), miss_capture=capture)
    result = answer(AnswerRequest(question=question), deps)
    return result, capture


def test_out_of_capability_question_is_captured_with_shape_and_detail():
    # The offline extractor maps an unmodeled question to shape="novel" → out_of_capability.
    result, capture = _run_with_capture("what is the airspeed of a swallow?")
    assert isinstance(result, OutOfCapabilityResult)
    assert len(capture) == 1
    miss = capture.misses[0]
    assert miss.shape == "novel"
    assert miss.question == "what is the airspeed of a swallow?"
    assert miss.detail  # carries the out_of_capability reason for later rule authoring
    assert capture.summary() == {"novel": 1}


def test_answerable_question_records_no_miss():
    # A normal answer is not a capability gap — nothing is captured.
    result, capture = _run_with_capture("how heavy is a sea otter?")
    assert result.outcome == "answer"
    assert len(capture) == 0


def test_capture_is_opt_in_and_off_by_default():
    # Without a collector the pipeline still answers; no capture machinery is required.
    result = answer(
        AnswerRequest(question="what is the airspeed of a swallow?"), build_offline_deps()
    )
    assert isinstance(result, OutOfCapabilityResult)
