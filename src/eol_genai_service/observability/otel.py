"""OpenTelemetry exporter behind the span sink (T002b — Constitution Principle VI).

The tracing scaffold (:mod:`eol_genai_service.observability.tracing`) collects layer-tagged
:class:`~eol_genai_service.observability.tracing.Span` records into an optional sink. This module is
the seam that drains that sink into an OpenTelemetry backend: each of our spans becomes an OTel span
carrying its ``layer`` (``service-extractor`` vs ``client-orchestrator``), model id, token/cost
counters, and measured latency — so latency, cost, and errors stay attributable per layer once the
spans reach any OTLP/console/in-memory exporter.

This module is intentionally *not* imported by ``observability/__init__`` — importing the base
package never requires OpenTelemetry; only callers that actually export pull it in. The caller owns
the exporter choice (OTLP for prod, console for dev, in-memory for tests) and keeps the returned
provider alive for the lifetime of the process.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import Status, StatusCode, Tracer

from eol_genai_service.observability.tracing import Span

_INSTRUMENTATION = "eol_genai_service"


def build_tracer_provider(exporter: SpanExporter) -> TracerProvider:
    """A provider wired to ``exporter`` via a simple (synchronous) processor.

    Synchronous export keeps span ordering deterministic for tests and avoids a background flush;
    swap in a ``BatchSpanProcessor`` at the composition root for production throughput.
    """
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider


def get_tracer(provider: TracerProvider) -> Tracer:
    """The service tracer from ``provider``."""
    return provider.get_tracer(_INSTRUMENTATION)


def export_spans(tracer: Tracer, spans: Iterable[Span]) -> None:
    """Emit each collected :class:`Span` as an OTel span, preserving layer attribution."""
    for s in spans:
        _export_one(tracer, s)


def _export_one(tracer: Tracer, s: Span) -> None:
    # Reconstruct the span's wall-clock window from its measured latency so the OTel span's duration
    # matches what we recorded (the authoritative value is also kept as the `latency_ms` attribute).
    end_ns = time.time_ns()
    start_ns = end_ns - int(s.latency_ms * 1_000_000)
    otel = tracer.start_span(s.name, start_time=start_ns)
    otel.set_attribute("layer", s.layer.value)
    if s.model_id is not None:
        otel.set_attribute("model_id", s.model_id)
    otel.set_attribute("tokens_in", s.tokens_in)
    otel.set_attribute("tokens_out", s.tokens_out)
    otel.set_attribute("cost", s.cost)
    otel.set_attribute("latency_ms", s.latency_ms)
    for key, value in s.attributes.items():
        otel.set_attribute(f"attr.{key}", _attr_value(value))
    if s.error is not None:
        otel.set_attribute("error", s.error)
        otel.set_status(Status(StatusCode.ERROR, s.error))
    else:
        otel.set_status(Status(StatusCode.OK))
    otel.end(end_time=end_ns)


def _attr_value(value: object) -> str | bool | int | float:
    """Coerce an arbitrary attribute value to an OTel-accepted scalar."""
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)
