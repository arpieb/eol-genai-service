# Implementation Plan: EOL Trait Query Service

**Branch**: `001-eol-trait-query` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-eol-trait-query/spec.md`

## Summary

Expose a service that answers natural-language biodiversity questions against the Encyclopedia
of Life (EOL) trait graph, returning correct, sourced, structured results — clients never write
or see Cypher. The design is two-tier with a single hard validator between everything and EOL:
a service-side, tightly-scoped LLM (Mellea constrained decoding) handles NL→intent extraction,
term/taxon resolution, deterministic repair, and a catalog of versioned query shapes; the
external calling model orchestrates the rare novel multi-hop long tail by chaining set-valued
single-hop tool calls. The dominant technical problem is term→URI grounding, solved by retrieval
over an embedded catalog of the graph's own predicate/value terms — never by trusting the model
to recall ontology URIs.

## Technical Context

**Language/Version**: Python 3.14+ (`uv`-managed; pinned by `.python-version` / `requires-python`)

**Primary Dependencies**: FastAPI + Pydantic (client-facing contract endpoint and typed models);
Mellea (constrained decoding → format-valid intent objects); Anthropic SDK (general frontier
Claude model for the scoped service-side extractor/judge); an embeddings model + local persisted
vector index (term→URI grounding); `httpx` (EOL Cypher client); MCP server SDK (tool surface for
the calling model); OpenTelemetry (layer-tagged tracing)

**Storage**: No service-owned primary datastore. A local, persisted **embedded term catalog**
(predicate + value `Term`s) and a **term-list cache**, both rebuildable from the self-describing
EOL graph. EOL/neo4j is upstream, read-only.

**Testing**: `pytest` via `uv run pytest`. Validator and template contract tests (positive +
negative); a golden hand-written-query accuracy harness (SC-001); a labeled ambiguity set
(SC-004); a truncation-flagging suite (SC-005)

**Target Platform**: Linux server (containerized)

**Project Type**: Single backend service with a tool/MCP surface (single project)

**Performance Goals**: p95 ≤ 5 s end-to-end for canonical-shape questions US-1–US-5 (SC-006);
term/taxon resolution served from the cached embedded catalog, not live upstream calls

**Constraints**: One shared admin-issued JWT to EOL (not per-user); `LIMIT` mandatory on every
query; ontology URIs are case-sensitive; strictly read-only; deliberate result-size caps with
explicit truncation flagging; empty results are valid answers; aggressive caching to protect a
small 2018-era upstream

**Scale/Scope**: 8 user-story shapes (US-1–US-8); predicate/value term catalog on the order of
10^3–10^5 terms; novel multi-hop questions are a rare long tail

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.0.0. All seven principles map to concrete
design elements; no violations.

| # | Principle | How this plan satisfies it | Gate |
|---|-----------|----------------------------|------|
| I | Service Owns the Contract | `contract/` Pydantic models are the only boundary; neo4j `cypher`/`csv` output is mapped, never passed through; upstream schema/return-shape changes are absorbed in `upstream/` + mappers | PASS |
| II | One Validator, No Bypass | Single `validator/` module asserts LIMIT-present, all-URIs-resolved, read-only; both the in-service template path and the calling-model tool path call `run_cypher`, which refuses to execute anything that has not cleared the validator | PASS |
| III | Determinism for the Known, LLM for the Novel | `shapes/` holds versioned, testable templates for US-1–US-5 and anticipated n-hop chains; free-form LLM generation is reserved for the unanticipated long tail and is never the default for a modeled shape | PASS |
| IV | General Model + Domain Retrieval | Reasoning uses a general frontier Claude model; all domain specificity lives in the embedded term catalog (`resolution/`); term→URI grounding is retrieval, not fine-tuning | PASS |
| V | Scoped Model Authority | The service-side LLM is confined to extraction, term/taxon resolution, repair, and ambiguity judgment; novel multi-hop planning stays with the calling model (`orchestration/` exposes single-hop tools, not an agent) | PASS |
| VI | Observability Is Not Optional | `observability/` tags every span with its layer (`client-orchestrator` vs `service-extractor`) from day one; latency, cost, and errors are layer-attributable | PASS |
| VII | Respect the Upstream | `upstream/` caches term lists, enforces deliberate result caps, treats empty as valid (FR-010), and bounds retries with backoff (FR-013); no tight retry loops | PASS |

**Result**: PASS (initial). Re-evaluated post-Phase 1 — see "Post-Design Constitution Re-Check".

## Project Structure

### Documentation (this feature)

```text
specs/001-eol-trait-query/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── client-contract.md      # NL question in → structured result out (the boundary)
│   ├── tools.md                # resolve_predicate / resolve_taxon / run_cypher / discovery
│   ├── validator.md            # the single validator's contract
│   └── upstream-cypher.md      # EOL endpoint contract + neo4j→contract mapping
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify, /speckit-clarify)
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created here)
```

### Source Code (repository root)

```text
src/eol_genai_service/
├── contract/            # Principle I — Pydantic request/result models; outcome variants
│   ├── requests.py      #   structured intent + raw NL question input
│   └── results.py       #   answer | no-records | needs-clarification | upstream-unavailable | out-of-capability
├── extraction/          # Principle V — Mellea-constrained NL→intent extractor (scoped LLM)
├── resolution/          # Principle IV — retrieval-based grounding
│   ├── index.py         #   build/query the embedded term catalog (rebuildable from the graph)
│   ├── predicates.py    #   resolve_predicate(text) → candidate Terms {name, uri, type}
│   └── taxa.py          #   resolve_taxon(name) → page_id (prefer EOL page/search lookup)
├── shapes/              # Principle III — versioned, testable query templates (known shapes + n-hop chains)
├── repair/              # Principle III — versioned deterministic repair rules + miss capture
├── validator/           # Principle II — single shared validator: LIMIT, URIs resolved, read-only
├── upstream/            # Principle VII — EOL Cypher client: JWT, format, caching, caps, read-only, error mapping
├── orchestration/       # set-valued single-hop execution; server-side n-hop chain assembly under one LIMIT
├── tools/               # MCP/tool surface for the calling model (wraps resolution + run_cypher)
├── observability/       # Principle VI — layer-tagged tracing (latency, cost, error attribution)
├── api/                 # FastAPI app exposing the client contract endpoint
└── config.py            # settings: JWT, model ids, caps, cache TTLs, endpoint

tests/
├── contract/            # validator rules, template shapes, client-contract conformance
├── integration/         # end-to-end per user story (US-1..US-8); upstream stubbed/recorded
└── unit/                # resolution, repair rules, mappers
```

**Structure Decision**: Single-project Python service (`src/` + `tests/`) — Option 1. There is no
separate frontend; the "client-side calling model" is an external consumer of the contract/tool
surface, not code in this repo. Module boundaries are drawn to make each constitution principle
enforceable in isolation (the validator is one module with one entry point; the contract is one
package; domain knowledge is confined to `resolution/`).

## Complexity Tracking

> No constitution violations — no entries required.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)    | —          | —                                   |

## Post-Design Constitution Re-Check

After Phase 1 (data-model, contracts, quickstart), re-evaluated all seven gates: still PASS. The
contracts reinforce rather than weaken the principles — `client-contract.md` keeps Cypher/neo4j
shapes off the boundary (I); `validator.md` defines the single choke point both paths share (II);
`tools.md` keeps the single-hop surface set-valued and non-agentic, holding multi-hop planning on
the client (V); `upstream-cypher.md` codifies caching, caps, read-only, and bounded retry (VII).
No new complexity or deviation introduced.
