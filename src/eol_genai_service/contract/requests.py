"""Request models for the client-facing contract (T006).

See contracts/client-contract.md. Disambiguation is stateless: a prior ``needs_clarification``
response is resolved by re-submitting with ``chosen`` (FR-014).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChosenSelection(BaseModel):
    """A disambiguation choice echoed back from a prior ``needs_clarification`` result."""

    kind: Literal["taxon", "predicate"]
    page_id: int | None = None  # set when kind == "taxon"
    uri: str | None = None  # set when kind == "predicate" (case-sensitive)


class AnswerRequest(BaseModel):
    """An unstructured natural-language biodiversity question (FR-001)."""

    question: str = Field(min_length=1)
    chosen: ChosenSelection | None = None
