"""Layer-tagged tracing scaffold (T007 — Constitution Principle VI).

Every unit of work is wrapped in a :func:`span` carrying its ``layer`` so latency, cost, and
errors are attributable per layer (``service-extractor`` vs ``client-orchestrator``). This is a
dependency-light scaffold (stdlib only) with a stable surface; an OpenTelemetry exporter wires
in behind :class:`Span` later without changing call sites.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum

_log = logging.getLogger("eol_genai_service.trace")


class Layer(str, Enum):
    """Which reasoning layer produced an artifact (Constitution Principle VI)."""

    SERVICE_EXTRACTOR = "service-extractor"
    CLIENT_ORCHESTRATOR = "client-orchestrator"


@dataclass
class Span:
    """A single traced operation with layer attribution."""

    name: str
    layer: Layer
    model_id: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)


@contextmanager
def span(
    name: str,
    layer: Layer,
    *,
    model_id: str | None = None,
    sink: list[Span] | None = None,
) -> Iterator[Span]:
    """Open a layer-tagged span, timing the block and capturing any error.

    The caller may set ``tokens_in``/``tokens_out``/``cost`` on the yielded span for LLM calls.
    If ``sink`` is provided, the completed span is appended to it (the seam an OpenTelemetry
    exporter or in-memory collector plugs into).
    """
    s = Span(name=name, layer=layer, model_id=model_id)
    start = time.perf_counter()
    try:
        yield s
    except Exception as exc:  # noqa: BLE001 - record then re-raise so errors stay attributable
        s.error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        s.latency_ms = (time.perf_counter() - start) * 1000.0
        _log.debug(
            "span layer=%s name=%s latency_ms=%.1f model=%s tokens_in=%d tokens_out=%d error=%s",
            s.layer.value,
            s.name,
            s.latency_ms,
            s.model_id,
            s.tokens_in,
            s.tokens_out,
            s.error,
        )
        if sink is not None:
            sink.append(s)


@dataclass
class LayerTotals:
    """Aggregated attribution for one layer."""

    spans: int = 0
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    errors: int = 0


def totals_by_layer(spans: list[Span]) -> dict[Layer, LayerTotals]:
    """Attribute latency, tokens, cost, and errors to each layer (Constitution Principle VI)."""
    out: dict[Layer, LayerTotals] = {}
    for s in spans:
        t = out.setdefault(s.layer, LayerTotals())
        t.spans += 1
        t.latency_ms += s.latency_ms
        t.tokens_in += s.tokens_in
        t.tokens_out += s.tokens_out
        t.cost += s.cost
        t.errors += 1 if s.error else 0
    return out
