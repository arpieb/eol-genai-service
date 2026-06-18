# System Architecture

The EOL Trait Query Service answers natural-language biodiversity questions against the
Encyclopedia of Life (EOL) trait graph and returns **structured, sourced** results. Clients
never write or see Cypher.

It is a **two-tier** design with a **single hard validator** between everything and EOL:

- a **service-side, tightly-scoped LLM** path (the FastAPI `/v1/answer` contract) handles the
  known canonical shapes (US-1–US-5) deterministically: NL→intent extraction, term/taxon
  resolution by retrieval, a catalog of versioned query shapes, and deterministic repair;
- an **external calling model** orchestrates the rare novel multi-hop long tail (US-7) by
  composing read-only single-hop tools exposed over **MCP**.

Both paths reach EOL **only** through `run_cypher`, which runs the one validator first
(Constitution Principle II — One Validator, No Bypass).

```mermaid
flowchart TB
    %% ─────────────── Clients ───────────────
    subgraph clients["Clients"]
        httpClient["HTTP client<br/>(curl / app)"]
        callingModel["External calling model<br/>(orchestrates novel multi-hop)"]
    end

    %% ─────────────── Entry surfaces ───────────────
    subgraph entry["Entry surfaces"]
        api["api/app.py<br/>FastAPI · POST /v1/answer<br/><i>Principle I — contract boundary</i>"]
        mcp["tools/server.py<br/>FastMCP · stdio | streamable-http | sse"]
    end

    %% ─────────────── Service core ───────────────
    subgraph core["Service core"]
        pipeline["orchestration/pipeline.py<br/>answer(): extract → resolve → route → map"]
        surface["tools/surface.py · ToolSurface<br/>resolve · discover · single_hop · n_hop_chain<br/><i>Principle V — no multi-hop planner</i>"]

        subgraph scoped["Scoped LLM + domain retrieval"]
            extraction["extraction/<br/>Mellea-constrained<br/>NL → Intent"]
            resolution["resolution/<br/>predicate (embeddings) ·<br/>taxon (EOL search API)<br/><i>Principle IV</i>"]
        end

        subgraph deterministic["Deterministic query construction"]
            shapes["shapes/<br/>versioned templates:<br/>attribute · association ·<br/>aggregate_count · lineage · n_hop_chain"]
            repair["repair/<br/>deterministic rules<br/>+ miss capture"]
        end
    end

    %% ─────────────── The one choke point ───────────────
    runcypher["upstream/run_cypher.py<br/><b>THE ONLY PATH TO EOL</b>"]
    validator["validator/core.py<br/>LIMIT present · all URIs resolved · read-only<br/><i>Principle II — single validator</i>"]

    %% ─────────────── Upstream boundary ───────────────
    subgraph upstream["Upstream boundary (Principle VII)"]
        client["upstream/client.py · EolCypherClient<br/>JWT · result cap + truncation · bounded retry"]
        transport["upstream/http_transport.py<br/>httpx · neo4j {columns,data} → rows"]
        mappers["upstream/mappers.py<br/>neo4j rows → contract Statements"]
    end

    %% ─────────────── External ───────────────
    subgraph external["External systems (read-only)"]
        eolCypher["EOL Cypher endpoint<br/>eol.org/service/cypher"]
        eolSearch["EOL search / pages API"]
        embedBackend["Embeddings backend<br/>(Ollama / litellm)"]
    end

    %% ─────────────── Cross-cutting ───────────────
    contract["contract/<br/>Pydantic requests + 5 result outcomes"]
    observability["observability/<br/>layer-tagged OTel spans"]
    config["config.py · factory.py<br/>composition root (live vs offline)"]

    %% ── Flows ──
    httpClient --> api --> pipeline
    callingModel -->|MCP tool calls| mcp --> surface

    pipeline --> extraction
    pipeline --> resolution
    pipeline --> shapes
    pipeline --> repair
    surface --> resolution
    surface --> shapes

    resolution -.taxon.-> eolSearch
    resolution -.embed.-> embedBackend

    pipeline --> runcypher
    surface --> runcypher
    runcypher --> validator
    runcypher --> client
    client --> transport --> eolCypher
    client --> mappers

    api -.returns.-> contract
    pipeline -.maps via.-> mappers
    pipeline -. spans .-> observability
    surface -. spans .-> observability
    config -.builds.-> pipeline
    config -.builds.-> surface

    classDef choke fill:#ffe6e6,stroke:#cc0000,stroke-width:2px;
    classDef ext fill:#eef5ff,stroke:#3366cc;
    class runcypher,validator choke;
    class eolCypher,eolSearch,embedBackend ext;
```

## Layer responsibilities

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Contract boundary | `api/app.py`, `contract/` | NL question in → one of five structured outcomes out. Cypher/neo4j never cross it (Principle I). |
| MCP tool surface | `tools/server.py`, `tools/surface.py` | Read-only tools for the external calling model. No write tool, no multi-hop planner (Principle V). |
| Orchestration | `orchestration/pipeline.py` | `extract → resolve → route → build → run_cypher → map`. Confidence-gated; low confidence → `needs_clarification`. |
| Scoped LLM | `extraction/` | Mellea constrained decoding: NL → format-valid `Intent`. |
| Domain retrieval | `resolution/` | Term→URI and name→page_id grounding by retrieval over the embedded catalog + EOL search API (Principle IV). |
| Query shapes | `shapes/` | Versioned, testable templates for the known shapes + anticipated n-hop chains (Principle III). |
| Validator | `validator/core.py` | Single entry point: LIMIT present, every URI resolved, read-only (Principle II). |
| Upstream | `upstream/` | The only network boundary to EOL: JWT, caps + truncation flag, bounded retry, error mapping (Principle VII). |
| Cross-cutting | `observability/`, `config.py`, `factory.py` | Layer-tagged tracing; composition root chooses live vs offline deps. |

## The five outcomes

Every `/v1/answer` request resolves to exactly one: `answer`, `no_records`,
`needs_clarification`, `upstream_unavailable`, `out_of_capability`.
