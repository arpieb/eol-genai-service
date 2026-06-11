"""neo4j → contract mappers (T015 / T022).

Translate raw EOL rows into service ``Statement``s — the boundary mapping (Constitution
Principle I). No neo4j row shape escapes past here. ``single_fact`` rows carry a normalized
measurement, mapped to a :class:`QuantitativeValue` (FR-005), with provenance attached (FR-004).
"""

from __future__ import annotations

from collections.abc import Sequence

from eol_genai_service.contract import (
    Predicate,
    Provenance,
    QuantitativeValue,
    Statement,
    Taxon,
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


def _provenance(row: dict[str, object]) -> Provenance:
    resource = None
    if row.get("resource_name") is not None:
        resource = {"id": row.get("resource_id"), "name": row.get("resource_name")}
    citation = row.get("citation")
    return Provenance(resource=resource, citation=str(citation) if citation else None)
