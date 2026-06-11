---
description: "Task list for EOL Trait Query Service implementation"
---

# Tasks: EOL Trait Query Service

**Input**: Design documents from `/specs/001-eol-trait-query/`

**Prerequisites**: plan.md, spec.md (required); research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED. The spec defines success criteria as hard test gates (SC-001–SC-006) and the
constitution mandates positive+negative validator coverage, so test tasks are first-class here.

**Organization**: Tasks are grouped by user story (priority order from spec.md) for independent
implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to spec user stories (US1=US-1 … US8=US-8)
- Paths are relative to repo root; package root is `src/eol_genai_service/`

## Path Conventions

- Single project: `src/eol_genai_service/`, `tests/` at repository root (per plan.md Structure Decision)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and structure

- [X] T001 Create package + test structure (`src/eol_genai_service/{contract,extraction,resolution,shapes,repair,validator,upstream,orchestration,tools,observability,api}/__init__.py` and `tests/{contract,integration,unit}/`)
- [ ] T002 Add runtime dependencies via `uv add fastapi pydantic httpx mellea anthropic opentelemetry-sdk opentelemetry-api mcp` (update `pyproject.toml` + `uv.lock`)
- [ ] T003 [P] Add embeddings + vector-index deps via `uv add` per research.md R2 (e.g. `voyageai` and/or `sentence-transformers` + `faiss-cpu` or `sqlite-vec`)
- [X] T004 [P] Add dev tooling via `uv add --dev pytest ruff` and configure lint/format in `pyproject.toml`
- [X] T005 [P] Scaffold settings in `src/eol_genai_service/config.py` (EOL JWT, `EOL_CYPHER_URL`, model ids, result cap, cache TTLs, embeddings selection)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The cross-cutting cores every user story depends on — the contract boundary, the single
validator, the upstream client, resolution/grounding, extraction, and tracing.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Define contract models (the boundary, Principle I) in `src/eol_genai_service/contract/requests.py` and `src/eol_genai_service/contract/results.py`: `AnswerRequest`, `Result` union (answer/no_records/needs_clarification/upstream_unavailable/out_of_capability), `Statement`, `Value` union, `Taxon`, `Predicate`, `Provenance`, `CandidateSet`
- [X] T007 [P] Layer-tagged tracing scaffold (Principle VI) in `src/eol_genai_service/observability/tracing.py`: span helper attaching `layer` (`service-extractor`/`client-orchestrator`), `model_id`, token/cost/latency
- [X] T008 [P] EOL upstream client skeleton (Principle VII) in `src/eol_genai_service/upstream/client.py`: JWT header, `query`/`format=cypher` params, read-only transport, result cap + `truncated`, timeout/error → `upstream_unavailable`, bounded retry with backoff (no tight loop)
- [X] T009 [P] Single validator (Principle II) in `src/eol_genai_service/validator/core.py`: `validate(query, resolved_uris) -> Verdict` asserting LIMIT present, all URIs ∈ resolved set (case-sensitive), read-only (per contracts/validator.md)
- [X] T010 `run_cypher` no-bypass wiring in `src/eol_genai_service/upstream/run_cypher.py`: validator FIRST, execute only on positive verdict, single path to EOL (depends on T008, T009)
- [ ] T011 Embedded term catalog in `src/eol_genai_service/resolution/index.py`: enumerate predicate/value `Term`s from the graph, embed, persist, query (build + lookup) per research.md R1/R2
- [X] T012 [P] `resolve_predicate(text)` in `src/eol_genai_service/resolution/predicates.py` returning ranked `Term` candidates with scores (depends on T011)
- [X] T013 [P] `resolve_taxon(name)` in `src/eol_genai_service/resolution/taxa.py`, preferring EOL page/search lookup over name matching (FR-003) (depends on T008, T011)
- [ ] T014 Mellea-constrained extractor (Principle V) in `src/eol_genai_service/extraction/extract.py`: NL → `QueryIntent` (shape/taxon_refs/predicate_refs/rollup/direction_hint/hops) (depends on T006)
- [X] T015 [P] neo4j→contract mapper in `src/eol_genai_service/upstream/mappers.py`: 4 value slots → `Value.kind`, provenance attach, `truncated`/`count` (depends on T006)
- [ ] T016 [P] Versioned shape + repair registries in `src/eol_genai_service/shapes/registry.py` and `src/eol_genai_service/repair/rules.py` (id+version, testable lookup)
- [X] T017 Request pipeline + FastAPI `POST /v1/answer` in `src/eol_genai_service/api/app.py` wiring extract→resolve→shape→validator→run_cypher→map→Result (depends on T006, T010, T014, T015, T016)
- [X] T018 [P] Validator contract tests (SC-002, SC-003 hard gates) in `tests/contract/test_validator.py`: positive + negative for MISSING_LIMIT, UNRESOLVED_URI, NOT_READ_ONLY; assert zero upstream call on violation (depends on T009, T010)

**Checkpoint**: Foundation ready — user stories can now proceed.

---

## Phase 3: User Story 1 - Single fact about a taxon (US-1) (Priority: P1) 🎯 MVP

**Goal**: Ask a single-attribute question, get the quantitative measurement with units + provenance,
or an explicit no-record answer.

**Independent Test**: "how heavy is a sea otter?" returns body-mass value(s) with units + source
matching a hand-written query; a taxon with no mass record returns `no_records`.

- [X] T019 [P] [US1] Integration test in `tests/integration/test_us1_single_fact.py`: quantitative answer + provenance; no-record path → `no_records`
- [X] T020 [P] [US1] Client-contract conformance test (invariants C1–C4) in `tests/contract/test_client_contract.py`
- [X] T021 [US1] `single_fact` versioned shape template in `src/eol_genai_service/shapes/single_fact.py` (LIMIT mandatory)
- [X] T022 [US1] Quantitative `Value` mapping (amount/units/normalized from `normal_measurement`) in `src/eol_genai_service/upstream/mappers.py`
- [X] T023 [US1] Register `single_fact` in the shape registry and route `shape=single_fact` through the pipeline in `src/eol_genai_service/api/app.py`

**Checkpoint**: US-1 fully functional and independently testable (MVP).

---

## Phase 4: User Story 6 - Disambiguation (US-6) (Priority: P1)

**Goal**: When a taxon/predicate cannot be confidently resolved, return candidates instead of guessing.

**Independent Test**: A common name mapping to multiple taxa yields `needs_clarification` with a
candidate list; resubmitting with `chosen` proceeds to an answer.

- [X] T024 [P] [US6] Ambiguity-set integration test (SC-004 hard gate, 100%) in `tests/integration/test_us6_disambiguation.py`
- [X] T025 [US6] Confidence thresholds + `CandidateSet` assembly in `src/eol_genai_service/resolution/predicates.py` and `src/eol_genai_service/resolution/taxa.py`
- [X] T026 [US6] Stateless clarification branch in `src/eol_genai_service/api/app.py`: low confidence → `needs_clarification`; honor `request.chosen` on resubmit (FR-014)

**Checkpoint**: US-6 ensures no silent guessing across all stories.

---

## Phase 5: User Story 8 - No data (US-8) (Priority: P1)

**Goal**: A well-formed question with no EOL records returns explicit `no_records`, once, no retry loop.

**Independent Test**: A resolved question with empty upstream result returns `no_records` (distinct
from `upstream_unavailable`), single call, no retry.

- [X] T027 [P] [US8] Integration test in `tests/integration/test_us8_no_data.py`: empty upstream → `no_records`; assert single call, no retry on empty
- [X] T028 [US8] Empty-rows → `no_records` mapping (distinct from `upstream_unavailable`) and no-retry-on-empty rule in `src/eol_genai_service/upstream/run_cypher.py`

**Checkpoint**: Empty vs. unavailable vs. error are cleanly distinct.

---

## Phase 6: User Story 2 - Categorical attribute (US-2) (Priority: P2)

**Goal**: Categorical questions return controlled-term value(s) + provenance.

**Independent Test**: "what habitat does the raccoon live in?" returns categorical habitat term(s)
with provenance matching a hand-written query.

- [ ] T029 [P] [US2] Integration test in `tests/integration/test_us2_categorical.py`
- [ ] T030 [US2] `categorical_attribute` versioned shape in `src/eol_genai_service/shapes/categorical_attribute.py`
- [ ] T031 [US2] `object_term` → categorical `Value` mapping in `src/eol_genai_service/upstream/mappers.py` and "categorical-queried-as-numeric → read object_term" repair rule in `src/eol_genai_service/repair/rules.py`

**Checkpoint**: US-1 + US-2 both independently functional.

---

## Phase 7: User Story 3 - Ecological association (US-3) (Priority: P2)

**Goal**: Interaction questions return partner taxa in the correct direction + provenance.

**Independent Test**: "what do sea otters eat?" returns prey (not predators) with provenance and
correct `direction`, verified against a hand-written query.

- [ ] T032 [P] [US3] Integration test in `tests/integration/test_us3_association.py` asserting direction = prey (FR-011)
- [ ] T033 [US3] `association` versioned shape with direction assertion in `src/eol_genai_service/shapes/association.py`
- [ ] T034 [US3] `object_page` → taxon `Value` mapping w/ mandatory `direction`, plus "inverted-direction → flip & re-assert" repair rule in `src/eol_genai_service/repair/rules.py`

**Checkpoint**: US-1..US-3 independently functional.

---

## Phase 8: User Story 4 - Aggregate / count (US-4) (Priority: P3)

**Goal**: Counting questions return a count rolled up over attribute sub-types.

**Independent Test**: "how many taxa have a recorded body size?" returns a count including size
sub-types (wingspan, body mass), matching a hand-written roll-up query.

- [ ] T035 [P] [US4] Integration test in `tests/integration/test_us4_aggregate.py` (roll-up correctness, FR-006)
- [ ] T036 [US4] `aggregate_count` versioned shape using `-[:parent_term|synonym_of*0..]->` in `src/eol_genai_service/shapes/aggregate_count.py`
- [ ] T037 [US4] `count` payload mapping + "missing roll-up → add traversal" repair rule in `src/eol_genai_service/repair/rules.py`

**Checkpoint**: US-1..US-4 independently functional.

---

## Phase 9: User Story 5 - Lineage (US-5) (Priority: P3)

**Goal**: Ancestry questions return the lineage up the parent chain.

**Independent Test**: Ancestry of a known taxon returns the ordered parent chain to the root.

- [ ] T038 [P] [US5] Integration test in `tests/integration/test_us5_lineage.py`
- [ ] T039 [US5] `lineage` versioned shape (parent-chain traversal, LIMIT mandatory) in `src/eol_genai_service/shapes/lineage.py`

**Checkpoint**: All canonical shapes (US-1..US-5) independently functional.

---

## Phase 10: User Story 7 - Novel multi-step question (US-7) (Priority: P3)

**Goal**: Compositional questions are answered by chaining single-hop calls or returned as
`out_of_capability` — never a fabricated answer.

**Independent Test**: A compositional question returns a correctly composed answer or
`out_of_capability`; never a confident wrong answer.

- [ ] T040 [P] [US7] Integration test in `tests/integration/test_us7_novel.py` (composed answer OR `out_of_capability`; no fabrication)
- [ ] T041 [US7] Set-valued `single_hop(page_ids:set, predicate_uri, direction)` in `src/eol_genai_service/orchestration/single_hop.py` (set-in/set-out, `truncated`, per-hop direction assertion — guards R7's three failure modes)
- [ ] T042 [US7] MCP/tool surface in `src/eol_genai_service/tools/server.py` exposing `resolve_predicate`, `resolve_taxon`, `run_cypher`, `single_hop`, `list_predicates`, `get_schema` (read-only; no plan-multi-hop tool, Principle V)
- [ ] T043 [US7] Server-side `n_hop_chain` parameterized shape (single LIMIT, `WITH DISTINCT … carry page … next predicate`) in `src/eol_genai_service/shapes/n_hop_chain.py`
- [ ] T044 [US7] `out_of_capability` routing for novel beyond modeled chains in `src/eol_genai_service/api/app.py`

**Checkpoint**: Full long-tail handling; "never confidently wrong" holds.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Success-criteria hard gates, upstream-care, and observability assertions across stories.

- [ ] T045 [P] SC-001 accuracy harness vs hand-written golden queries (≥90% over US-1..US-5) in `tests/integration/test_accuracy_golden.py`
- [ ] T046 [P] SC-005 truncation suite (flag always set; no silent partial, incl. per-hop) in `tests/integration/test_truncation.py`
- [ ] T047 [P] SC-006 latency check (p95 ≤ 5 s, warm cache) in `tests/integration/test_latency.py`
- [ ] T048 [P] Term-list cache TTL/invalidation + catalog rebuild command (Principle VII) in `src/eol_genai_service/resolution/index.py`
- [ ] T049 [P] Repair-loop miss capture to grow the rule set (research.md R8) in `src/eol_genai_service/repair/capture.py`
- [ ] T050 [P] Observability assertions (layer tags + per-layer cost/latency attribution) in `tests/integration/test_observability.py`
- [ ] T051 [P] Run quickstart.md validation pass and update docs/README
- [ ] T052 [P] FR-013 upstream-unavailable integration test in `tests/integration/test_upstream_unavailable.py`: timeout / 5xx / transport error → `upstream_unavailable` outcome, asserted **distinct** from `no_records` (US-8) and internal errors; verify bounded retry-with-backoff occurs and is **not** a tight loop

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; BLOCKS all user stories. Internal order: T006 →
  (T007, T008, T009 parallel) → T010 → T011 → (T012, T013 parallel) → T014/T015/T016 → T017 → T018.
- **User Stories (Phases 3–10)**: all depend on Foundational. After that they are largely
  independent and may proceed in parallel; P1 (US-1, US-6, US-8) first for MVP.
- **Polish (Phase 11)**: depends on the user stories it measures (accuracy/latency need US-1..US-5;
  truncation needs the shapes; observability spans all).

### User Story Dependencies

- **US-1 (P1)**: Foundational only. MVP.
- **US-6 (P1)**: Foundational only (touches resolution + pipeline branch).
- **US-8 (P1)**: Foundational only (touches `run_cypher` mapping).
- **US-2 / US-3 (P2)**: Foundational only; independent of each other.
- **US-4 / US-5 (P3)**: Foundational only; independent.
- **US-7 (P3)**: Foundational only; adds the tool surface + n-hop shape (does not modify earlier shapes).

### Within Each User Story

- Tests are written first and expected to FAIL before implementation.
- Shape template → value mapping/repair rule → pipeline routing.

### Parallel Opportunities

- Setup: T003, T004, T005 in parallel.
- Foundational: T007, T008, T009 in parallel; then T012, T013; then T015, T016.
- Across stories: once Phase 2 is done, the `[P]` test tasks (T019, T024, T027, T029, T032, T035,
  T038, T040) can all be authored in parallel, and different stories implemented by different people.
- Polish: T045–T052 all `[P]`.

---

## Parallel Example: Foundational core

```bash
# After T006 (contract models) lands, launch the three independent cores together:
Task: "Layer-tagged tracing scaffold in src/eol_genai_service/observability/tracing.py"   # T007
Task: "EOL upstream client skeleton in src/eol_genai_service/upstream/client.py"           # T008
Task: "Single validator in src/eol_genai_service/validator/core.py"                        # T009
```

## Parallel Example: P1 story tests

```bash
# Once Foundational completes, author the P1 story tests in parallel:
Task: "US-1 integration test in tests/integration/test_us1_single_fact.py"                 # T019
Task: "US-6 ambiguity integration test in tests/integration/test_us6_disambiguation.py"    # T024
Task: "US-8 no-data integration test in tests/integration/test_us8_no_data.py"             # T027
```

---

## Implementation Strategy

### MVP First (P1 stories)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) — the validator, upstream client, contract,
   resolution, and extraction must exist before any answer can be produced.
2. Complete Phase 3 (US-1) → **STOP and VALIDATE** the single-fact path end-to-end.
3. Add Phase 4 (US-6) and Phase 5 (US-8) to complete the P1 safety/coverage trio (no guessing, empty
   is valid). This is the demoable MVP.

### Incremental Delivery

- P2 (US-2 categorical, US-3 association) adds the remaining value shapes (categorical, taxon-valued
  with direction).
- P3 (US-4 count, US-5 lineage, US-7 novel) adds aggregation, hierarchy traversal, and the long-tail
  tool surface.
- Each story is independently testable and deployable; the hard-gate suites (SC-002/SC-003) run from
  Phase 2 onward and must stay green.

### Notes

- `[P]` tasks = different files, no incomplete dependencies.
- Every shape template carries a `LIMIT`; every query reaches EOL only through the validator (no bypass).
- Commit after each task or logical group; keep SC-002/SC-003 validator tests green at all times.
