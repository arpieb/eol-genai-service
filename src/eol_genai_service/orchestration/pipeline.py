"""Request pipeline (T017): extract → resolve → validate → run_cypher → map → Result.

Pure orchestration over injected dependencies, so it is fully testable offline and the live
extractor/resolvers/client drop in unchanged. Every query reaches EOL only through
``run_cypher`` (Constitution Principle II). Low-confidence resolution yields ``needs_clarification``
rather than a guess (FR-009 / US-6); the stateless resubmit path honors ``request.chosen``
(FR-014).
"""

from __future__ import annotations

from dataclasses import dataclass

from eol_genai_service.config import Settings
from eol_genai_service.contract import (
    AnswerRequest,
    AnswerResult,
    CandidateSet,
    NeedsClarificationResult,
    NoRecordsResult,
    OutOfCapabilityResult,
    Predicate,
    Result,
    Taxon,
    UpstreamUnavailableResult,
)
from eol_genai_service.contract import Statement
from eol_genai_service.extraction.extract import Extractor
from eol_genai_service.resolution.predicates import PredicateResolver
from eol_genai_service.resolution.taxa import TaxonResolver
from eol_genai_service.shapes.aggregate_count import build_aggregate_count_query
from eol_genai_service.shapes.association import association_direction, build_association_query
from eol_genai_service.shapes.categorical_attribute import build_categorical_query
from eol_genai_service.shapes.lineage import build_lineage_query
from eol_genai_service.shapes.single_fact import build_single_fact_query
from eol_genai_service.upstream.client import EolCypherClient, UpstreamUnavailable
from eol_genai_service.upstream.mappers import (
    map_association_rows,
    map_categorical_rows,
    map_lineage_rows,
    map_single_fact_rows,
)
from eol_genai_service.upstream.run_cypher import run_cypher

# Resolution must clear this confidence bar; otherwise we ask rather than guess (SC-004 hard gate).
CONFIDENCE_THRESHOLD = 0.85
# A second candidate within this margin of the top makes the choice ambiguous.
AMBIGUITY_MARGIN = 0.15

# The concrete query shape is chosen by the resolved predicate's type (FR-005), not guessed.
_SHAPE_BY_PREDICATE_TYPE = {
    "measurement": "single_fact",
    "categorical": "categorical_attribute",
    "association": "association",
}


@dataclass(frozen=True)
class PipelineDeps:
    extractor: Extractor
    predicate_resolver: PredicateResolver
    taxon_resolver: TaxonResolver
    client: EolCypherClient
    settings: Settings


def answer(request: AnswerRequest, deps: PipelineDeps) -> Result:
    """Answer one natural-language question, returning one of the five contract outcomes."""
    intent = deps.extractor.extract(request.question)
    if intent.shape == "novel":
        # No modeled single-hop shape matched (US-7 territory); never fabricate an answer.
        return OutOfCapabilityResult(reason="question is not a modeled single-hop shape")

    # Shapes that don't follow the "one taxon + one predicate" form get their own branch.
    if intent.shape == "aggregate_count":
        return _answer_count(intent, deps)
    if intent.shape == "lineage":
        return _answer_lineage(request, intent, deps)

    # A single-hop shape needs both a taxon and a predicate reference. An extractor may return
    # neither (e.g. an under-specified question); without something to ground, we cannot answer —
    # out_of_capability rather than guessing or erroring.
    if not intent.taxon_refs or not intent.predicate_refs:
        return OutOfCapabilityResult(reason="question lacks a taxon and/or attribute to resolve")

    # --- Resolve the taxon (honor a prior disambiguation choice first; FR-014) ---
    subject = _resolve_subject(request, intent, deps)
    if isinstance(subject, NeedsClarificationResult):
        return subject

    # --- Resolve the predicate ---
    predicate = _resolve_predicate(intent, deps)
    if isinstance(predicate, NeedsClarificationResult):
        return predicate

    # The concrete shape follows from the predicate type — read the correct value slot (FR-005).
    shape = _SHAPE_BY_PREDICATE_TYPE.get(predicate.type)
    if shape is None:
        return OutOfCapabilityResult(reason=f"predicate type {predicate.type!r} not modeled")

    # --- Build, validate, and execute (single path to EOL) ---
    cap = deps.settings.result_cap
    query = _build_query(shape, subject.page_id, predicate.uri, cap)
    try:
        upstream = run_cypher(query, {predicate.uri}, deps.client)
    except UpstreamUnavailable as exc:
        return UpstreamUnavailableResult(detail=str(exc))

    if not upstream.rows:
        return NoRecordsResult()

    statements = _map(shape, upstream.rows, subject, predicate)
    return AnswerResult(statements=statements, truncated=upstream.truncated, cap=cap)


def _answer_count(intent, deps: PipelineDeps) -> Result:
    """US-4: count taxa with a recorded value for a (rolled-up) predicate. No taxon involved."""
    if not intent.predicate_refs:
        return OutOfCapabilityResult(reason="count question lacks a recognizable attribute")
    predicate = _resolve_predicate(intent, deps)
    if isinstance(predicate, NeedsClarificationResult):
        return predicate
    cap = deps.settings.result_cap
    query = build_aggregate_count_query(predicate.uri, cap)
    try:
        upstream = run_cypher(query, {predicate.uri}, deps.client)
    except UpstreamUnavailable as exc:
        return UpstreamUnavailableResult(detail=str(exc))
    # A count is always an answer (zero is a valid count), never no_records.
    count = int(upstream.rows[0]["count"]) if upstream.rows else 0
    return AnswerResult(statements=[], count=count, truncated=upstream.truncated, cap=cap)


def _answer_lineage(request: AnswerRequest, intent, deps: PipelineDeps) -> Result:
    """US-5: return a taxon's ancestor chain. No predicate involved (graph traversal, no URI)."""
    if request.chosen is None and not intent.taxon_refs:
        return OutOfCapabilityResult(reason="lineage question lacks a recognizable taxon")
    subject = _resolve_subject(request, intent, deps)
    if isinstance(subject, NeedsClarificationResult):
        return subject
    cap = deps.settings.result_cap
    query = build_lineage_query(subject.page_id, cap)
    try:
        upstream = run_cypher(query, set(), deps.client)  # no ontology URI to resolve
    except UpstreamUnavailable as exc:
        return UpstreamUnavailableResult(detail=str(exc))
    if not upstream.rows:
        return NoRecordsResult()
    return AnswerResult(
        statements=map_lineage_rows(upstream.rows, subject),
        truncated=upstream.truncated,
        cap=cap,
    )


def _build_query(shape: str, page_id: int, uri: str, cap: int) -> str:
    if shape == "single_fact":
        return build_single_fact_query(page_id, uri, cap)
    if shape == "categorical_attribute":
        return build_categorical_query(page_id, uri, cap)
    return build_association_query(page_id, uri, cap)


def _map(shape: str, rows, subject: Taxon, predicate: Predicate) -> list[Statement]:
    if shape == "single_fact":
        return map_single_fact_rows(rows, subject, predicate)
    if shape == "categorical_attribute":
        return map_categorical_rows(rows, subject, predicate)
    return map_association_rows(rows, subject, predicate, association_direction(predicate.uri))


def _resolve_subject(
    request: AnswerRequest, intent, deps: PipelineDeps
) -> Taxon | NeedsClarificationResult:
    if request.chosen is not None and request.chosen.kind == "taxon" and request.chosen.page_id:
        taxon = deps.taxon_resolver.by_page_id(request.chosen.page_id)
        if taxon is not None:
            return taxon
    if not intent.taxon_refs:  # no extracted taxon and no valid choice — nothing to resolve
        return NeedsClarificationResult(candidates=CandidateSet(kind="taxon", items=[]))
    candidates = deps.taxon_resolver.resolve(intent.taxon_refs[0])
    if _is_confident(candidates):
        top = candidates[0]
        return Taxon(
            page_id=top.page_id,
            scientific_name=top.scientific_name,
            vernacular_names=top.vernacular_names,
        )
    return NeedsClarificationResult(
        candidates=CandidateSet(kind="taxon", items=_contending(candidates))
    )


def _resolve_predicate(intent, deps: PipelineDeps) -> Predicate | NeedsClarificationResult:
    candidates = deps.predicate_resolver.resolve(intent.predicate_refs[0])
    if _is_confident(candidates):
        top = candidates[0]
        return Predicate(uri=top.uri, name=top.name, type=top.type)
    return NeedsClarificationResult(
        candidates=CandidateSet(kind="predicate", items=_contending(candidates))
    )


def _is_confident(candidates: list) -> bool:
    """Confident iff exactly one strong candidate (above threshold, no close runner-up)."""
    if not candidates or candidates[0].score < CONFIDENCE_THRESHOLD:
        return False
    if len(candidates) > 1 and candidates[0].score - candidates[1].score < AMBIGUITY_MARGIN:
        return False
    return True


def _contending(candidates: list) -> list:
    """The genuinely-competing candidates to present for clarification — those within the
    ambiguity margin of the top. Weak partial matches are not shown to the user."""
    if not candidates:
        return []
    cutoff = candidates[0].score - AMBIGUITY_MARGIN
    return [c for c in candidates if c.score >= cutoff]
