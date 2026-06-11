"""Layer-tagged tracing scaffold (T007 — Constitution Principle VI).

Every unit of work is wrapped in a :func:`span` carrying its ``layer`` so latency, cost, and
errors are attributable per layer (``service-extractor`` vs ``client-orchestrator``). This is a
dependency-light scaffold (stdlib only) with a stable surface; an OpenTelemetry exporter wires
in behind :class:`Span` later without changing call sites.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from collections.abc import Iterator


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
def span(name: str, layer: Layer, *, model_id: str | None = None) -> Iterator[Span]:
    """Open a layer-tagged span, timing the block and capturing any error.

    The caller may set ``tokens_in``/``tokens_out``/``cost`` on the yielded span for LLM calls.
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
