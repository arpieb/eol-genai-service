# Contract: The Single Validator (No Bypass)

One module, one entry point. The only gate between any query and EOL (Constitution II). Both the
in-service template path and the calling-model tool path reach EOL exclusively through `run_cypher`,
which calls this validator first and refuses to execute on any non-positive verdict.

## Entry point

`validate(query: str, resolved_uris: set[str]) -> Verdict`

```
Verdict = { ok: bool, violations: [Violation] }
Violation.code ∈ { MISSING_LIMIT, UNRESOLVED_URI, NOT_READ_ONLY }
```

## Assertions (all must hold for `ok = true`)

1. **`MISSING_LIMIT`** — the query MUST contain an explicit `LIMIT` clause. (Upstream also requires
   it; we assert locally so the guarantee is testable and pre-network.)
2. **`UNRESOLVED_URI`** — every ontology URI literal in the query MUST be a member of
   `resolved_uris` (the set produced by `resolve_predicate`/`resolve_taxon`). Any URI not traceable
   to resolution → reject (no model-invented URIs). Comparison is **case-sensitive**.
3. **`NOT_READ_ONLY`** — the query MUST contain no write clause:
   `CREATE | SET | DELETE | REMOVE | MERGE | DETACH | CALL { ... } ` mutations, etc. Read-only only.

## Invariants (testable)

- **V1**: `run_cypher` calls `validate` before any network I/O; a negative verdict prevents the call
  entirely (proven by a test that asserts zero upstream calls on each violation type).
- **V2**: Each assertion has positive **and** negative test coverage (constitution Development
  Workflow gate; e.g., a query missing `LIMIT`, a query citing a non-resolved URI, a query with a
  `SET`).
- **V3**: There is exactly **one** code path to EOL execution and it is guarded by this validator
  (no alternate client, no direct `httpx` call outside `upstream/run_cypher`).
- **V4**: Server-side mutation rejection by EOL is treated as defense-in-depth and does **not**
  substitute for assertion 3.

## Relationship to success criteria

- Backs **SC-002** (zero unresolved/invented URIs ever reach EOL — hard gate) via assertion 2.
- Backs **SC-003** (zero upstream mutations attempted — hard gate) via assertion 3 + V1 (the call
  is blocked locally before it is even attempted).
