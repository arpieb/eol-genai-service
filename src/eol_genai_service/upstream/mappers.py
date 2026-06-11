"""neo4j → contract mappers (T015 / T022 / T031 / T034).

Translate raw EOL rows into service ``Statement``s — the boundary mapping (Constitution
Principle I). No neo4j row shape escapes past here. Each value slot maps to its contract value
kind (FR-005): ``normal_measurement`` → quantitative, ``object_term`` → categorical,
``object_page`` → taxon (with asserted direction, FR-011). Provenance is attached (FR-004).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from eol_genai_service.contract import (
    CategoricalValue,
    Predicate,
    Provenance,
    QuantitativeValue,
    Statement,
    Taxon,
    TaxonValue,
)


def map_single_fact_rows(
    rows: Sequence[dict[str, object]], subject: Taxon, predicate: Predicate
) -> list[Statement]:
    """Map measurement rows to quantitative statements with provenance.

    The subject taxon and predicate come from resolution (already validated); rows supply the
    measurement value and provenance fields.
    """
    statements: list[Statement] = []
    for row in rows:
        statements.append(
            Statement(
                subject=subject,
                predicate=predicate,
                value=QuantitativeValue(
                    amount=float(row["amount"]),  # type: ignore[arg-type]
                    units=str(row["units"]),
                    normalized=True,
                ),
                provenance=_provenance(row),
            )
        )
    return statements


def map_categorical_rows(
    rows: Sequence[dict[str, object]], subject: Taxon, predicate: Predicate
) -> list[Statement]:
    """Map ``object_term`` rows to categorical statements (US-2, FR-005)."""
    statements: list[Statement] = []
    for row in rows:
        term = Predicate(uri=str(row["term_uri"]), name=str(row["term_name"]), type="categorical")
        statements.append(
            Statement(
                subject=subject,
                predicate=predicate,
                value=CategoricalValue(term=term),
                provenance=_provenance(row),
            )
        )
    return statements


def map_association_rows(
    rows: Sequence[dict[str, object]],
    subject: Taxon,
    predicate: Predicate,
    direction: Literal["subject_to_object", "object_to_subject"],
) -> list[Statement]:
    """Map ``object_page`` rows to taxon-valued statements with direction (US-3, FR-011)."""
    statements: list[Statement] = []
    for row in rows:
        partner = Taxon(
            page_id=int(row["partner_page_id"]),  # type: ignore[arg-type]
            scientific_name=str(row["partner_name"]),
        )
        statements.append(
            Statement(
                subject=subject,
                predicate=predicate,
                value=TaxonValue(taxon=partner, direction=direction),
                provenance=_provenance(row),
            )
        )
    return statements


def _provenance(row: dict[str, object]) -> Provenance:
    resource = None
    if row.get("resource_name") is not None:
        resource = {"id": row.get("resource_id"), "name": row.get("resource_name")}
    citation = row.get("citation")
    return Provenance(resource=resource, citation=str(citation) if citation else None)
