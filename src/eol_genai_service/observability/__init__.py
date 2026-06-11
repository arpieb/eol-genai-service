"""Layer-tagged observability (Constitution Principle VI)."""

from eol_genai_service.observability.tracing import (
    Layer,
    LayerTotals,
    Span,
    span,
    totals_by_layer,
)

__all__ = ["Layer", "LayerTotals", "Span", "span", "totals_by_layer"]
