"""MCP stdio server binding (US-7 / T042): the read-only tool surface is exposed correctly.

Drives the FastMCP server in-process (list_tools / call_tool) over an offline surface — no stdio, no
network. Asserts the surface is bound read-only (the contract invariants T1/T3/T4) and that calls
round-trip, including that run_cypher stays validator-gated through the MCP boundary (no bypass).
"""

import asyncio
import json

import pytest

from eol_genai_service.fixtures import build_offline_tool_surface
from eol_genai_service.tools.server import create_server
from eol_genai_service.tools.surface import FORBIDDEN_METHODS

_EXPECTED_TOOLS = {
    "resolve_predicate",
    "resolve_taxon",
    "list_predicates",
    "get_schema",
    "run_cypher",
    "single_hop",
    "n_hop_chain",
}


def _server():
    return create_server(build_offline_tool_surface())


def _tool_names(srv) -> set[str]:
    return {t.name for t in asyncio.run(srv.list_tools())}


def _call(srv, name: str, args: dict):
    # FastMCP returns (content, structured) for list-returning tools (structured wraps the value
    # under "result") but only the content blocks for dict-returning tools — handle both.
    res = asyncio.run(srv.call_tool(name, args))
    if isinstance(res, tuple):
        structured = res[1]
        return structured.get("result", structured)
    return json.loads(res[0].text)


def test_exposes_exactly_the_read_only_surface():
    names = _tool_names(_server())
    assert names == _EXPECTED_TOOLS
    # T3/T4: no write capability and no multi-hop planner is ever exposed (Principle V).
    assert not (names & FORBIDDEN_METHODS)
    assert not any(
        bad in n
        for n in names
        for bad in ("write", "set", "delete", "create", "plan", "orchestrate")
    )


def test_resolve_predicate_round_trips():
    result = _call(_server(), "resolve_predicate", {"text": "how heavy"})
    assert result[0]["uri"] == "VT_0001259"  # catalog-authoritative URI, model never authors it
    assert result[0]["type"] == "measurement"


def test_discovery_tools_return_catalog_and_schema():
    srv = _server()
    predicates = _call(srv, "list_predicates", {})
    assert {p["name"] for p in predicates} >= {"body mass", "habitat"}
    assert all({"uri", "name", "type"} <= p.keys() for p in predicates)

    schema = _call(srv, "get_schema", {})
    assert "Page" in schema["node_types"]
    assert "object_term" in schema["value_slots"]


def test_run_cypher_stays_validator_gated_through_mcp():
    # The only path to EOL: a query missing LIMIT must be rejected before any upstream call —
    # the no-bypass guarantee (Principle II) survives the MCP binding.
    srv = _server()
    with pytest.raises(Exception) as exc:
        _call(srv, "run_cypher", {"query": "MATCH (p:Page) RETURN p", "resolved_uris": []})
    assert "MISSING_LIMIT" in str(exc.value) or "validator" in str(exc.value).lower()
