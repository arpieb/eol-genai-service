"""Principle VI: the request path emits layer-tagged spans (C1 — observability wired in)."""

from dataclasses import replace

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.observability import Layer, Span, totals_by_layer
from eol_genai_service.orchestration.pipeline import answer


def _run_collecting_spans(question: str) -> list[Span]:
    sink: list[Span] = []
    deps = replace(build_offline_deps(), span_sink=sink)
    answer(AnswerRequest(question=question), deps)
    return sink


def test_request_emits_extract_and_run_cypher_spans_tagged_by_layer():
    sink = _run_collecting_spans("how heavy is a sea otter?")
    names = {s.name for s in sink}
    assert "extract" in names
    assert "run_cypher" in names
    # Every span is attributed to a reasoning layer (Principle VI).
    assert all(isinstance(s.layer, Layer) for s in sink)
    totals = totals_by_layer(sink)
    assert Layer.SERVICE_EXTRACTOR in totals
    assert totals[Layer.SERVICE_EXTRACTOR].latency_ms >= 0.0


def test_extract_span_carries_the_service_model_id():
    sink = _run_collecting_spans("how heavy is a sea otter?")
    extract = next(s for s in sink if s.name == "extract")
    assert extract.layer is Layer.SERVICE_EXTRACTOR
    assert extract.model_id == "granite4.1:3b"  # the configured service extractor model


def test_no_sink_still_answers(monkeypatch):
    # span_sink defaults to None; tracing still emits to the logger, the request still answers.
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), build_offline_deps())
    assert result.outcome == "answer"
