# Contract: Tool / MCP Surface

Tools the **calling model** uses to orchestrate the novel multi-hop long tail (Constitution V).
The service-side known-shape path uses the same resolution + `run_cypher` internals, so guarantees
are identical on both paths. Every tool emits a layer-tagged span (Constitution VI).

## `resolve_predicate(text) -> [Term]`

- **In**: `text` (free attribute phrasing, e.g., "how heavy").
- **Out**: ranked `[{ name, uri, type, score }]` from the embedded term catalog (R1/R2).
- **Guarantees**: URIs are catalog-authoritative and case-preserved; the model never authors a URI.
  Returns `[]` rather than inventing a match.

## `resolve_taxon(name) -> { page_id, scientific_name, candidates? }`

- **In**: `name` (scientific or common).
- **Out**: best `page_id` + `scientific_name`; on ambiguity, a ranked `candidates` list (FR-003).
- **Guarantees**: prefers EOL page/search lookup over canonical-name string matching to reduce
  homonym error; never returns a fabricated `page_id`.

## `run_cypher(query) -> { rows | upstream_error }`  (the only path to EOL)

- **In**: a Cypher `query` string.
- **Behavior**: submits to `validator` FIRST; executes against the endpoint only on a positive
  verdict; attaches the shared JWT + `format`; enforces read-only; applies result caps; maps
  upstream timeout/error to `upstream_error`.
- **Guarantees** (Constitution II/VII): rejects any query lacking `LIMIT`, referencing an
  unresolved/invented URI, or containing a write clause — **before** the network call. Empty rows
  are a valid return, not an error. Never passes neo4j shapes back unmapped to the boundary.

## `single_hop(page_ids: set, predicate_uri, direction) -> { results: set, truncated }`  (set-valued)

- **In**: a **set** of `page_id`s, a resolved `predicate_uri`, and a `direction`.
- **Out**: a **set** of result ids/values + `truncated` flag.
- **Guarantees** (R7): set-in/set-out so chaining never fans out into hundreds of single-entity
  calls; intermediate ids are structured data, never prose; per-hop truncation is surfaced, never
  silent; `direction` is asserted at every hop (no inversion).

## `list_predicates() -> [Term]` / `get_schema() -> SchemaSummary`  (discovery)

- Read-only discovery helpers backed by the cached catalog (Constitution VII — no live upstream
  hit at call time when the cache is warm).

## Invariants (testable)

- **T1**: No tool returns a result without passing through `validator` before any EOL execution.
- **T2**: `single_hop` signatures are set-typed on both input and output (cardinality guard, R7).
- **T3**: No tool surfaces a write capability; the surface is strictly read-only (Constitution II).
- **T4**: The tool surface exposes single hops + resolution only — no "plan a multi-hop chain" tool
  (Constitution V; multi-hop planning stays with the calling model or a versioned server-side
  `n_hop_chain` shape).
