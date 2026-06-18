# Documentation

Architecture and call-flow diagrams for the EOL Trait Query Service. All diagrams are
[Mermaid](https://mermaid.js.org/) in fenced code blocks and render natively on GitHub.

## Diagrams

- [**System Architecture**](architecture.md) — a layered view of the whole system: the two
  client tiers (HTTP `/v1/answer` and the MCP tool surface), the service core (orchestration,
  scoped LLM extraction, retrieval-based resolution, deterministic query shapes), the single
  validator choke point, and the read-only EOL upstream boundary.

- [**MCP Call Sequence**](mcp-sequence.md) — a sequence diagram tracing an external calling
  model's tool call through every major layer (FastMCP → ToolSurface → resolution/shapes →
  `run_cypher` → validator → client → transport → EOL), plus transport selection
  (`stdio | streamable-http | sse`).

## See also

- [`../README.md`](../README.md) — quickstart, user stories, and the five response outcomes.
- [`../specs/001-eol-trait-query/`](../specs/001-eol-trait-query/) — governing spec, plan,
  research, data model, and contracts.
- [`../.specify/memory/constitution.md`](../.specify/memory/constitution.md) — the seven
  principles the architecture enforces.
