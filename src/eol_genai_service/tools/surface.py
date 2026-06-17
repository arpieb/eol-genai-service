"""The tool surface for the calling model (T042 — Constitution Principle V).

The *external* calling model orchestrates the novel long tail by composing these read-only tools.
The surface exposes resolution, a validator-gated ``run_cypher``, a set-valued ``single_hop``,
``n_hop_chain`` for anticipated chains, and discovery helpers — but deliberately **no
"plan-a-multi-hop-chain" tool**: novel multi-hop planning stays with the calling model, keeping the
service model on a short leash (Principle V). Every tool reaches EOL only through ``run_cypher``,
so the single validator still gates everything (Principle II).

This module is the substance an MCP server would register; the MCP/stdio binding is a thin adapter
added with the ``mcp`` dependency at the composition root.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from eol_genai_service.contract import Predicate, PredicateCandidate, TaxonCandidate
from eol_genai_service.orchestration.pipeline import PipelineDeps
from eol_genai_service.shapes.n_hop_chain import (
    build_n_hop_chain_query,
    build_set_hop_query,
)
from eol_genai_service.upstream.run_cypher import run_cypher


@dataclass(frozen=True)
class HopResult:
    """Result of a set-valued single hop: a set of page_ids and whether it was truncated."""

    page_ids: frozenset[int]
    truncated: bool


@dataclass(frozen=True)
class ChainResult:
    """Terminal page_ids (+ names) of an n-hop chain, computed server-side under one LIMIT."""

    page_ids: tuple[int, ...]
    names: tuple[str, ...]
    truncated: bool


@dataclass(frozen=True)
class SchemaSummary:
    """A controlled-vocabulary view of the graph for orchestration — not raw neo4j/Cypher."""

    node_types: tuple[str, ...]
    statement_pattern: str
    value_slots: tuple[str, ...]


DEFAULT_SCHEMA = SchemaSummary(
    node_types=("Page", "Trait", "Term", "Resource", "Vernacular", "MetaData"),
    statement_pattern="(:Page)-[:trait|inferred_trait]->(:Trait)-[:predicate]->(:Term)",
    value_slots=("object_term", "object_page", "normal_measurement", "literal"),
)


class ToolSurface:
    """Read-only tools the calling model composes. No write capability, no multi-hop planner."""

    def __init__(
        self, deps: PipelineDeps, predicates: Sequence[Predicate], schema: SchemaSummary
    ) -> None:
        self._deps = deps
        self._predicates = tuple(predicates)
        self._schema = schema

    # --- resolution ---------------------------------------------------------------------------
    def resolve_predicate(self, text: str) -> list[PredicateCandidate]:
        return self._deps.predicate_resolver.resolve(text)

    def resolve_taxon(self, name: str) -> list[TaxonCandidate]:
        return self._deps.taxon_resolver.resolve(name)

    # --- discovery ----------------------------------------------------------------------------
    def list_predicates(self) -> list[Predicate]:
        return list(self._predicates)

    def get_schema(self) -> SchemaSummary:
        return self._schema

    # --- execution (validator-gated, set-valued) ----------------------------------------------
    def run_cypher(self, query: str, resolved_uris: set[str]):
        """Execute a query — but only through the single validator (no bypass)."""
        return run_cypher(query, resolved_uris, self._deps.client)

    def single_hop(self, page_ids: set[int], predicate_uri: str, direction: str) -> HopResult:
        """One association hop over a SET of page_ids, returning a SET (R7 cardinality guard).

        ``direction`` is honored in the query (no silent inversion, FR-011) — the builder rejects an
        invalid value.
        """
        cap = self._deps.settings.result_cap
        query = build_set_hop_query(page_ids, predicate_uri, cap, direction)
        result = run_cypher(query, {predicate_uri}, self._deps.client)
        partners = frozenset(int(r["partner_page_id"]) for r in result.rows)
        return HopResult(page_ids=partners, truncated=result.truncated)

    def n_hop_chain(self, start_page_id: int, hops: Sequence[tuple[str, str]]) -> ChainResult:
        """Run an anticipated N-hop chain server-side under a single LIMIT (R7 truncation guard)."""
        cap = self._deps.settings.result_cap
        query = build_n_hop_chain_query(start_page_id, hops, cap)
        resolved = {uri for uri, _ in hops}
        result = run_cypher(query, resolved, self._deps.client)
        page_ids = tuple(int(r["result_page_id"]) for r in result.rows)
        names = tuple(str(r["result_name"]) for r in result.rows)
        return ChainResult(page_ids=page_ids, names=names, truncated=result.truncated)


# The surface must never grow a server-side multi-hop planner (Principle V) — asserted in tests.
FORBIDDEN_METHODS: frozenset[str] = frozenset({"plan_multi_hop", "plan_chain", "orchestrate"})
