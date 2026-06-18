"""MCP stdio server exposing the read-only tool surface (US-7 / T042 / T002b — Constitution V).

A thin adapter: it registers each :class:`ToolSurface` method as an MCP tool over stdio so an
external calling model can orchestrate the novel multi-hop long tail. Every tool is read-only and
reaches EOL only through ``run_cypher`` → the single validator (Principle II); there is deliberately
**no write tool and no "plan-a-multi-hop-chain" tool** (Principle V) — multi-hop planning stays with
the calling model or the versioned server-side ``n_hop_chain`` shape.

The substance lives in :mod:`eol_genai_service.tools.surface`; this module only binds it to MCP.
Build the live surface at the composition root (``build_live_surface``); tests inject an offline
surface into :func:`create_server`.
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from eol_genai_service.tools.surface import DEFAULT_SCHEMA, ToolSurface

_INSTRUCTIONS = (
    "Read-only tools over the EOL trait graph. Resolve attribute phrases and taxon names to "
    "catalog URIs / page ids (never author a URI yourself), then compose single hops or an "
    "anticipated n-hop chain. Every query reaches EOL only through run_cypher, which validates "
    "LIMIT + resolved URIs + read-only before any upstream call. Empty rows are a valid answer."
)


def build_live_surface() -> ToolSurface:
    """Assemble the live tool surface at the composition root (needs EOL_JWT + the cached index)."""
    from eol_genai_service.factory import build_deps

    deps = build_deps()
    return ToolSurface(deps, deps.predicate_resolver.catalog(), DEFAULT_SCHEMA)


def create_server(surface: ToolSurface) -> FastMCP:
    """Register the read-only tool surface as MCP tools. ``surface`` is injected (live or offline)."""
    mcp = FastMCP("eol-genai-service", instructions=_INSTRUCTIONS)

    @mcp.tool(
        description="Resolve an attribute phrase to ranked ontology predicate candidates "
        "{name, uri, type, score} from the catalog. Returns [] rather than inventing a URI."
    )
    def resolve_predicate(text: str) -> list[dict]:
        return [c.model_dump() for c in surface.resolve_predicate(text)]

    @mcp.tool(
        description="Resolve a taxon name (scientific or common) to ranked page candidates "
        "{page_id, scientific_name, score}. Never returns a fabricated page_id."
    )
    def resolve_taxon(name: str) -> list[dict]:
        return [c.model_dump() for c in surface.resolve_taxon(name)]

    @mcp.tool(
        description="List the controlled predicate catalog {uri, name, type} (cached; no "
        "upstream call)."
    )
    def list_predicates() -> list[dict]:
        return [p.model_dump() for p in surface.list_predicates()]

    @mcp.tool(
        description="A controlled-vocabulary summary of the graph for orchestration "
        "(node types, statement pattern, value slots) — not raw neo4j/Cypher."
    )
    def get_schema() -> dict:
        s = surface.get_schema()
        return {
            "node_types": list(s.node_types),
            "statement_pattern": s.statement_pattern,
            "value_slots": list(s.value_slots),
        }

    @mcp.tool(
        description="Execute a Cypher query — the ONLY path to EOL. The single validator runs "
        "first (LIMIT required, every URI must be in resolved_uris, read-only) before any "
        "network call. Returns {rows, truncated}; empty rows are valid."
    )
    def run_cypher(query: str, resolved_uris: list[str]) -> dict:
        result = surface.run_cypher(query, set(resolved_uris))
        return {"rows": result.rows, "truncated": result.truncated}

    @mcp.tool(
        description="One association hop over a SET of page_ids → a SET of partner page_ids "
        "(set-in/set-out so chaining never fans out). direction is asserted, never inverted. "
        "Returns {page_ids, truncated}."
    )
    def single_hop(page_ids: list[int], predicate_uri: str, direction: str) -> dict:
        result = surface.single_hop(set(page_ids), predicate_uri, direction)
        return {"page_ids": sorted(result.page_ids), "truncated": result.truncated}

    @mcp.tool(
        description="Run an anticipated N-hop predicate chain server-side under a SINGLE LIMIT "
        "(guards silent per-hop truncation). hops is a list of [predicate_uri, direction]. "
        "Returns {page_ids, names, truncated}."
    )
    def n_hop_chain(start_page_id: int, hops: list[list[str]]) -> dict:
        result = surface.n_hop_chain(start_page_id, [(uri, direction) for uri, direction in hops])
        return {
            "page_ids": list(result.page_ids),
            "names": list(result.names),
            "truncated": result.truncated,
        }

    return mcp


def transport_config() -> tuple[str, str, int]:
    """Transport selection from the environment.

    ``EOL_MCP_TRANSPORT`` ∈ ``stdio`` (default — local subprocess clients) | ``streamable-http``
    (the modern HTTP transport; serves the standard MCP endpoint at ``/mcp``) | ``sse`` (legacy
    HTTP). Host/port (HTTP transports only) come from ``EOL_MCP_HOST`` / ``EOL_MCP_PORT``.
    """
    return (
        os.getenv("EOL_MCP_TRANSPORT", "stdio"),
        os.getenv("EOL_MCP_HOST", "0.0.0.0"),
        int(os.getenv("EOL_MCP_PORT", "8765")),
    )


def build_http_app(server: FastMCP, transport: str):
    """The Starlette app for an HTTP MCP transport, wrapped in CORS so **browser-based** clients
    work: the streamable-http protocol round-trips a ``Mcp-Session-Id`` header, and browsers send a
    CORS preflight (``OPTIONS``) first — without CORS the preflight is rejected (405) and the
    session header isn't readable. ``EOL_MCP_PATH`` overrides the endpoint path (default ``/mcp``);
    ``EOL_MCP_CORS_ORIGINS`` is a comma-separated allowlist (default ``*``)."""
    from starlette.middleware.cors import CORSMiddleware

    path = os.getenv("EOL_MCP_PATH")
    if path:
        server.settings.streamable_http_path = path
        server.settings.sse_path = path
    app = server.streamable_http_app() if transport == "streamable-http" else server.sse_app()
    origins = [o.strip() for o in os.getenv("EOL_MCP_CORS_ORIGINS", "*").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],  # the streamable-http session id the client must read
    )
    return app


def main() -> None:
    """Run the live MCP server (``uv run eol-genai-mcp``). stdio by default; set
    ``EOL_MCP_TRANSPORT=streamable-http`` to serve the ``/mcp`` endpoint for networked clients."""
    transport, host, port = transport_config()
    server = create_server(build_live_surface())
    server.settings.host = host
    server.settings.port = port
    if transport == "stdio":
        server.run(transport="stdio")
        return
    import uvicorn

    uvicorn.run(build_http_app(server, transport), host=host, port=port)


if __name__ == "__main__":
    main()
