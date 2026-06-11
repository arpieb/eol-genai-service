# Quickstart & Validation Guide: EOL Trait Query Service

A runnable guide proving the feature works end-to-end. Implementation bodies live in `tasks.md` +
the implementation phase; this is a validation/run guide only.

## Prerequisites

- `uv` (project env manager) and Python 3.14+ (`uv sync` provisions the `.venv`).
- An EOL service **JWT** (request from the EOL maintainer) exported as a secret/env var.
- An embeddings provider key **or** the local-embeddings fallback enabled (see `research.md` R2).
- A built **term catalog index** (see "Build the catalog" below).

## Setup

```bash
uv sync                      # provision env from pyproject.toml + uv.lock
export EOL_JWT=...           # shared admin token (never per-user)
export EOL_CYPHER_URL=https://eol.org/service/cypher
# embeddings: either EMBEDDINGS_API_KEY=... or EOL_LOCAL_EMBEDDINGS=1
```

## Build the catalog (term→URI grounding)

Enumerate the graph's own predicate/value terms and embed them into the local index. This is the
domain knowledge (Constitution IV); it is rebuildable and cached, so query-time resolution never
hits EOL.

```bash
uv run python -m eol_genai_service.resolution.index build   # → persisted index artifact
```

## Run the service

```bash
uv run uvicorn eol_genai_service.api:app --reload           # client contract on /v1/answer
```

## Validation scenarios (map to user stories & success criteria)

Each scenario calls `POST /v1/answer` (see `contracts/client-contract.md`) and checks the `outcome`.

| # | Question | Expected `outcome` & check | Story / SC |
|---|----------|----------------------------|------------|
| 1 | "how heavy is a sea otter?" | `answer` with `value.kind=quantitative`, units, provenance | US-1 / SC-001 |
| 2 | a taxon with no mass record | `no_records` (explicit, not error) | US-1 / FR-010 |
| 3 | "what habitat does the raccoon live in?" | `answer` with `value.kind=categorical` + provenance | US-2 |
| 4 | "what do sea otters eat?" | `answer` with `value.kind=taxon`, `direction` = prey (not predators) | US-3 / FR-011 |
| 5 | "how many taxa have a recorded body size?" | `answer` with `count` rolled up over sub-types | US-4 / FR-006 |
| 6 | ancestry of a taxon | `answer` lineage up the parent chain | US-5 |
| 7 | an ambiguous common name | `needs_clarification` with candidate set (no guess) | US-6 / SC-004 |
| 8 | "which pollinators visit plants that humans use?" | composed `answer` **or** `out_of_capability` — never a fabricated answer | US-7 |
| 9 | well-formed question, empty upstream | `no_records`, returned once, no retry loop | US-8 / FR-010 |
| 10 | upstream down/timeout | `upstream_unavailable` (distinct from `no_records`) | FR-013 |

## Hard-gate checks (run in CI)

```bash
uv run pytest tests/contract/test_validator.py    # SC-002, SC-003: LIMIT / resolved-URI / read-only, +/- cases
uv run pytest tests/integration -k truncation     # SC-005: no silent truncation; truncated flag always set
uv run pytest tests/integration -k ambiguity      # SC-004: 100% of labeled ambiguity set → needs_clarification
uv run pytest tests/integration -k accuracy        # SC-001: ≥90% vs hand-written golden queries (US-1..US-5)
```

Expected outcomes:
- **SC-002 / SC-003**: zero queries with an invented URI or a write clause ever reach the client;
  the validator blocks them **before** any upstream call (`contracts/validator.md` V1).
- **SC-005**: every truncated result carries `truncated=true`; no silent partial answers.
- **SC-004**: every labeled-ambiguous input yields `needs_clarification` (100% hard gate).
- **SC-006**: p95 end-to-end latency ≤ 5 s for scenarios 1–6 with a warm catalog cache.

## Observability check (Constitution VI)

After any scenario, confirm each request's trace carries layer tags (`service-extractor`, and
`client-orchestrator` for tool-driven multi-hop), with latency, token, and cost counters
attributable per layer.
