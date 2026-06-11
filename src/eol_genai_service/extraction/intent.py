"""QueryIntent — the format-valid typed object the extractor produces (data-model.md §3).

Internal to the service (never on the boundary). Semantic validity (real URIs/page_ids) is
established downstream by resolution and the validator, not by extraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Shape = Literal[
    "single_fact",
    "categorical_attribute",
    "association",
    "aggregate_count",
    "lineage",
    "n_hop_chain",
    "novel",
]


@dataclass(frozen=True)
class QueryIntent:
    """A typed parse of a natural-language question.

    ``shape != "novel"`` MUST be served by a versioned template (Constitution Principle III).
    Raw refs are resolved to URIs/page_ids before any query is built.
    """

    shape: Shape
    taxon_refs: tuple[str, ...] = field(default_factory=tuple)
    predicate_refs: tuple[str, ...] = field(default_factory=tuple)
    rollup: bool = False
