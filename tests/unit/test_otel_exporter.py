"""T002b: our layer-tagged spans export to an OpenTelemetry backend intact (Principle VI)."""

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from eol_genai_service.observability import Layer, Span
from eol_genai_service.observability.otel import (
    build_tracer_provider,
    export_spans,
    get_tracer,
)


def _exporter_and_tracer():
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(exporter)
    return exporter, get_tracer(provider)


def test_span_attributes_survive_export():
    exporter, tracer = _exporter_and_tracer()
    export_spans(
        tracer,
        [
            Span(
                name="extract",
                layer=Layer.SERVICE_EXTRACTOR,
                model_id="granite4.1:3b",
                tokens_in=120,
                tokens_out=30,
                cost=0.0,
                latency_ms=12.5,
                attributes={"shape": "single_fact"},
            )
        ],
    )
    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    s = finished[0]
    assert s.name == "extract"
    assert s.attributes["layer"] == "service-extractor"
    assert s.attributes["model_id"] == "granite4.1:3b"
    assert s.attributes["tokens_in"] == 120
    assert s.attributes["latency_ms"] == 12.5
    assert s.attributes["attr.shape"] == "single_fact"  # free-form attrs are namespaced
    assert s.status.status_code is StatusCode.OK
    # Duration reflects the recorded latency (~12.5 ms), reconstructed from start/end times.
    assert (s.end_time - s.start_time) == 12_500_000


def test_errored_span_exports_with_error_status():
    exporter, tracer = _exporter_and_tracer()
    export_spans(
        tracer,
        [Span(name="run_cypher", layer=Layer.SERVICE_EXTRACTOR, error="UpstreamUnavailable: 503")],
    )
    s = exporter.get_finished_spans()[0]
    assert s.status.status_code is StatusCode.ERROR
    assert s.attributes["error"] == "UpstreamUnavailable: 503"
