# Contract: Upstream EOL Cypher Endpoint (External, Fixed)

This is an **external** contract we consume, not one we expose. Documented so the mapping into our
own contract (Constitution I) and the upstream-care rules (Constitution VII) are explicit and
testable. Nothing here leaks past `upstream/`.

## Endpoint

`GET/POST https://eol.org/service/cypher`

| Param | Meaning |
|-------|---------|
| `query` | Cypher text (must include `LIMIT`) |
| `format` | `cypher` (native neo4j JSON, default) or `csv` |

- **Auth**: a single admin-issued **JWT** (request via the EOL maintainer), attached as a header.
  One shared service token — **not** per-user (R6).
- **Mutations**: rejected **server-side** (defense-in-depth; our validator is the primary guard).
- **`LIMIT`**: **required** by the service.
- **Case sensitivity**: ontology URIs carry uppercase; matches must respect case. No lower-casing in
  the client or mappers.
- **Disposition**: small, 2018-era. Cache aggressively; be gentle.

## Consumption rules (testable)

- **U1**: Request `format=cypher`; **map** results into service `Statement`/`Provenance`/`Value`
  entities. Never return `cypher`/`csv` payloads unchanged to the boundary (Constitution I).
- **U2**: Term lists enumerated for the catalog (`Term {type:"measurement"}`, `{type:"association"}`,
  value terms) are **cached** with explicit TTL/invalidation; query-time resolution hits the cache,
  not the upstream (Constitution VII; supports SC-006 latency).
- **U3**: Apply a deliberate **result cap**; set the contract `truncated` flag when hit (SC-005).
- **U4**: Map outcomes precisely:
  - empty rows → `no_records` (FR-010), **not** a retry and **not** an error;
  - timeout/5xx/transport error → `upstream_unavailable` (FR-013), distinct from `no_records` and
    from internal errors;
  - bounded retries with backoff only (no tight loop).
- **U5**: The four Trait value slots (`object_term`, `object_page`, `normal_measurement`, `literal`)
  map to `Value.kind` (`categorical`, `taxon`, `quantitative`, `literal`) — see `data-model.md` §1.
- **U6**: Roll-up traversal `-[:parent_term|synonym_of*0..]->` is applied when the intent's `rollup`
  flag is set (FR-006); association `direction` is asserted, never inverted (FR-011).
