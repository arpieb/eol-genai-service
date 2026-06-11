"""The client-facing contract — the only boundary clients depend on (Constitution Principle I).

Cypher, the EOL schema, and neo4j return shapes never appear here. See
specs/001-eol-trait-query/contracts/client-contract.md and data-model.md §2.
"""

from eol_genai_service.contract.requests import AnswerRequest, ChosenSelection
from eol_genai_service.contract.results import (
    AnswerResult,
    CandidateSet,
    CategoricalValue,
    LiteralValue,
    NeedsClarificationResult,
    NoRecordsResult,
    OutOfCapabilityResult,
    Predicate,
    PredicateCandidate,
    Provenance,
    QuantitativeValue,
    Result,
    Statement,
    Taxon,
    TaxonCandidate,
    TaxonValue,
    UpstreamUnavailableResult,
)

__all__ = [
    "AnswerRequest",
    "ChosenSelection",
    "AnswerResult",
    "CandidateSet",
    "CategoricalValue",
    "LiteralValue",
    "NeedsClarificationResult",
    "NoRecordsResult",
    "OutOfCapabilityResult",
    "Predicate",
    "PredicateCandidate",
    "Provenance",
    "QuantitativeValue",
    "Result",
    "Statement",
    "Taxon",
    "TaxonCandidate",
    "TaxonValue",
    "UpstreamUnavailableResult",
]
