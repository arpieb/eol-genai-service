"""Observability assertions (T050 — Constitution Principle VI).

Every span carries its layer; latency, tokens, cost, and errors are attributable per layer
(client-orchestrator vs service-extractor).
"""

import pytest

from eol_genai_service.observability import Layer, Span, span, totals_by_layer


def test_spans_carry_their_layer_and_are_collected():
    sink: list[Span] = []
    with span("extract", Layer.SERVICE_EXTRACTOR, model_id="claude-sonnet-4-6", sink=sink) as s:
        s.tokens_in, s.tokens_out, s.cost = 100, 20, 0.001
    assert len(sink) == 1
    assert sink[0].layer is Layer.SERVICE_EXTRACTOR
    assert sink[0].model_id == "claude-sonnet-4-6"
    assert sink[0].latency_ms >= 0.0


def test_cost_and_tokens_attributable_per_layer():
    sink: list[Span] = []
    with span("extract", Layer.SERVICE_EXTRACTOR, sink=sink) as s:
        s.tokens_in, s.tokens_out, s.cost = 100, 20, 0.001
    with span("orchestrate", Layer.CLIENT_ORCHESTRATOR, sink=sink) as s:
        s.tokens_in, s.tokens_out, s.cost = 300, 50, 0.004

    totals = totals_by_layer(sink)
    assert totals[Layer.SERVICE_EXTRACTOR].tokens_in == 100
    assert totals[Layer.CLIENT_ORCHESTRATOR].tokens_in == 300
    assert totals[Layer.CLIENT_ORCHESTRATOR].cost == pytest.approx(0.004)
    assert set(totals) == {Layer.SERVICE_EXTRACTOR, Layer.CLIENT_ORCHESTRATOR}


def test_errors_are_recorded_and_attributed():
    sink: list[Span] = []
    with pytest.raises(ValueError):
        with span("extract", Layer.SERVICE_EXTRACTOR, sink=sink):
            raise ValueError("boom")
    assert sink[0].error is not None
    assert totals_by_layer(sink)[Layer.SERVICE_EXTRACTOR].errors == 1
