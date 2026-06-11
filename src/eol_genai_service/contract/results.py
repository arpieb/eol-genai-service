"""Result models for the client-facing contract (T006).

Five first-class outcomes, none overloaded onto an error: ``answer``, ``no_records``,
``needs_clarification``, ``upstream_unavailable``, ``out_of_capability``. See data-model.md §2
and contracts/client-contract.md. No field here carries Cypher, a neo4j row, or an EOL schema
label (Constitution Principle I; invariant C1).
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class Taxon(BaseModel):
    """A stable taxon reference the service owns (FR-003)."""

    page_id: int
    scientific_name: str
    vernacular_names: list[dict[str, str]] = Field(default_factory=list)


class Predicate(BaseModel):
    """A resolved attribute backed by a controlled ontology term.

    ``uri`` is case-sensitive and MUST have come from resolution, never the model
    (Constitution Principle II — the validator enforces this on the query side).
    """

    uri: str
    name: str
    type: Literal["measurement", "association", "categorical"]


# --- Value: a tagged union by ``kind`` (FR-005) -------------------------------------------------


class QuantitativeValue(BaseModel):
    kind: Literal["quantitative"] = "quantitative"
    amount: float
    units: str
    normalized: bool = True


class CategoricalValue(BaseModel):
    kind: Literal["categorical"] = "categorical"
    term: Predicate


class TaxonValue(BaseModel):
    kind: Literal["taxon"] = "taxon"
    taxon: Taxon
    # Direction is mandatory and asserted across hops — never inverted (FR-011).
    direction: Literal["subject_to_object", "object_to_subject"]


class LiteralValue(BaseModel):
    kind: Literal["literal"] = "literal"
    text: str


Value = Annotated[
    Union[QuantitativeValue, CategoricalValue, TaxonValue, LiteralValue],
    Field(discriminator="kind"),
]


class Provenance(BaseModel):
    """Traceability for a statement (FR-004). Absence is explicit, never silently dropped."""

    resource: dict[str, object] | None = None
    contributor: str | None = None
    citation: str | None = None
    reference: str | None = None


class Statement(BaseModel):
    """One answer row."""

    subject: Taxon
    predicate: Predicate
    value: Value
    provenance: Provenance = Field(default_factory=Provenance)


# --- Disambiguation candidates (FR-009 / US-6) --------------------------------------------------


class TaxonCandidate(Taxon):
    score: float


class PredicateCandidate(Predicate):
    score: float


class CandidateSet(BaseModel):
    kind: Literal["taxon", "predicate"]
    items: list[Union[TaxonCandidate, PredicateCandidate]]


# --- Result: a tagged union by ``outcome`` ------------------------------------------------------


class AnswerResult(BaseModel):
    outcome: Literal["answer"] = "answer"
    statements: list[Statement] = Field(default_factory=list)
    count: int | None = None  # rolled-up aggregate for US-4 (FR-006)
    # ``truncated`` is always present; True iff a result cap was hit (SC-005). No silent truncation.
    truncated: bool = False
    cap: int


class NoRecordsResult(BaseModel):
    """EOL has no such record — a successful, explicit answer (FR-010 / US-8)."""

    outcome: Literal["no_records"] = "no_records"


class NeedsClarificationResult(BaseModel):
    """Resolution confidence was below threshold; ask rather than guess (FR-009 / US-6)."""

    outcome: Literal["needs_clarification"] = "needs_clarification"
    candidates: CandidateSet


class UpstreamUnavailableResult(BaseModel):
    """EOL was unavailable/timed out/errored — distinct from no_records (FR-013)."""

    outcome: Literal["upstream_unavailable"] = "upstream_unavailable"
    detail: str


class OutOfCapabilityResult(BaseModel):
    """A novel question outside current capability — never a fabricated answer (US-7)."""

    outcome: Literal["out_of_capability"] = "out_of_capability"
    reason: str


Result = Annotated[
    Union[
        AnswerResult,
        NoRecordsResult,
        NeedsClarificationResult,
        UpstreamUnavailableResult,
        OutOfCapabilityResult,
    ],
    Field(discriminator="outcome"),
]
