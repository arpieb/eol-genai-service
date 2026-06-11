<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.0 → 1.1.0
Rationale: MINOR — materially expanded guidance on model selection. Clarifies that
Principle IV's "general frontier LLM" requirement binds the client orchestrator and the
grounding pipeline, while the scoped service-side extractor (Principle V) MAY use a smaller
or locally-hosted constrained model (frontier configurable). No principle removed or
redefined; the contract, validator, determinism, retrieval, observability, and upstream
rules are unchanged.

Modified principles:
- IV. General Model + Domain Retrieval — added "Scope of the frontier-LLM requirement"
- V. Scoped Model Authority — added the small/local-model latitude note

Templates requiring updates:
- plan-template / spec-template / tasks-template — ✅ no change (model-agnostic)
- specs/001-eol-trait-query/research.md (R3) and src/eol_genai_service/config.py — updated to
  default the service extractor to a local Granite (Mellea/Ollama) backend, frontier configurable

Follow-up TODOs: none

---
PRIOR REPORT (v1.0.0)
=====================
Version change: (uninitialized template) → 1.0.0
Rationale: Initial ratification of the project constitution. MAJOR baseline (1.0.0)
because this establishes the governing principle set for the first time.

Modified principles:
- [PRINCIPLE_1] → I. Service Owns the Contract, Not the Query Language
- [PRINCIPLE_2] → II. One Validator, No Bypass
- [PRINCIPLE_3] → III. Determinism for the Known, LLM for the Novel
- [PRINCIPLE_4] → IV. General Model + Domain Retrieval, Not a Domain-Tuned Model
- [PRINCIPLE_5] → V. Scoped Model Authority
- (added)       → VI. Observability Is Not Optional
- (added)       → VII. Respect the Upstream

Added sections:
- Additional Constraints & Standards (was [SECTION_2_NAME])
- Development Workflow & Quality Gates (was [SECTION_3_NAME])

Removed sections: none

Templates requiring updates:
- .specify/templates/plan-template.md  ✅ no change needed (Constitution Check gate is
  dynamically derived from this file)
- .specify/templates/spec-template.md  ✅ no change needed (constitution-agnostic)
- .specify/templates/tasks-template.md ✅ no change needed (constitution-agnostic)
- CLAUDE.md                            ✅ no change needed (referenced as runtime guidance)

Follow-up TODOs: none
-->

# EOL GenAI Service Constitution

## Core Principles

### I. Service Owns the Contract, Not the Query Language

Clients exchange structured intent and structured results only. Cypher, the EOL graph
schema, and the neo4j return shape are internal implementation details and MUST NOT cross
the service boundary. No request or response field may expose query structure, EOL schema
identifiers, or raw neo4j row shapes. A change to query structure, the EOL schema, or the
neo4j return shape MUST be absorbable without altering the published contract.

**Rationale**: A stable intent/result contract lets EOL's internals and our query strategy
evolve freely; leaking them couples every client to details they must never depend on.

### II. One Validator, No Bypass

Every query — whether produced from a template or by an LLM — MUST pass through a single
shared validator before it reaches EOL. The validator MUST reject any query that: (a) lacks
an explicit `LIMIT`, (b) references an unresolved or model-invented ontology URI, or (c) is
not read-only. No code path may issue a query to EOL that has not cleared the validator.

**Rationale**: A single chokepoint is the only place where safety can actually be
guaranteed. Multiple paths to the upstream mean multiple ways to bypass every guarantee.

### III. Determinism for the Known, LLM for the Novel

Anticipated query shapes MUST be served by deterministic, versioned, independently testable
templates. Free-form LLM query generation is reserved for the genuinely unanticipated long
tail and MUST NOT be the default path for any shape already modeled by a template.

**Rationale**: Determinism is cheaper, faster, and verifiable. LLM generation is a fallback
for the unknown, not the foundation for the known.

### IV. General Model + Domain Retrieval, Not a Domain-Tuned Model

Reasoning and orchestration MUST use a general frontier LLM. Domain specificity MUST live in
retrieval over EOL's own term tables (embeddings), never in fine-tuned model weights.
Term→URI grounding — the hard problem — MUST be solved by retrieval, not training.

**Scope of the frontier-LLM requirement**: "Reasoning and orchestration" binds the *client
orchestrator* (planning the novel multi-hop long tail) and the grounding pipeline. The *scoped
service-side extractor* (Principle V) performs a narrow, constrained-decoded task — filling a
typed intent schema and spotting surface mentions, with retrieval doing the domain grounding —
and therefore MAY run on a smaller or locally-hosted constrained model. A general frontier
model remains a supported, configurable choice for the service extractor (e.g. for the hard
disambiguation/repair tail), but is NOT required for it.

**Rationale**: Retrieval keeps domain knowledge inspectable, hot-updatable, and decoupled
from model lifecycles; baking it into weights makes it opaque and expensive to change. The
frontier requirement is reserved for the work that actually needs frontier reasoning — novel
orchestration — not the bounded extraction step a small constrained model handles cheaply,
locally, and without an external dependency on the hot path.

### V. Scoped Model Authority

The service-side LLM is scoped to extraction, term resolution, and repair of shapes the
service owns. It MUST NOT grow into a general agent that plans novel multi-hop reasoning
chains; that work stays with the calling (client) model. The service model is kept on a
short leash. Because its task is narrow and constrained-decoded, this model MAY be small
and/or locally hosted (see Principle IV); a frontier model is configurable for the hard tail.

**Rationale**: A narrowly scoped service model is auditable and bounded. An open-ended one
becomes an unaccountable agent whose behavior cannot be reasoned about or tested.

### VI. Observability Is Not Optional

Two LLM layers exist: the client orchestrator and the service extractor. Every request MUST
be traced from day one with tags identifying which layer produced each artifact. Latency,
cost, and error attribution MUST be localizable to a specific layer.

**Rationale**: With two reasoning layers, un-attributed telemetry makes debugging, cost
control, and error analysis impossible. Tracing added later is tracing never added.

### VII. Respect the Upstream

The EOL service is small and old and MUST be treated as a constrained dependency. Term lists
MUST be cached, result sizes MUST be deliberately capped, and empty result sets MUST be
treated as valid answers — not failures, errors, or retry triggers.

**Rationale**: Protecting a fragile upstream preserves its availability for every consumer;
hammering it or misreading emptiness as failure degrades the whole system.

## Additional Constraints & Standards

- **Tooling**: The project is `uv`-managed on Python 3.14+. Dependencies are declared in
  `pyproject.toml` and locked in `uv.lock`; do not use `pip`/`venv` directly.
- **Contract versioning**: The structured intent/result contract is explicitly versioned.
  Any backward-incompatible change to it requires a new contract version, never an in-place
  redefinition (see Principle I).
- **Validator coverage**: The single validator (Principle II) is the trust boundary to EOL.
  Each of its assertions — `LIMIT` present, all URIs resolved, read-only — MUST have positive
  and negative test coverage.
- **Tracing stack**: Every request carries a correlation identifier and per-layer tags
  (`client-orchestrator`, `service-extractor`) so latency, cost, and errors are attributable
  per Principle VI.
- **Caching discipline**: Term lists are cached with explicit lifetime/invalidation; result
  caps are configured deliberately, not left unbounded (Principle VII).

## Development Workflow & Quality Gates

- **Templates are versioned artifacts**: Each deterministic query template (Principle III) is
  versioned and ships with tests; changes to a template bump its version.
- **Boundary review**: Any change touching query generation, the validator, the service
  contract, or the EOL/neo4j integration MUST demonstrate compliance with Principles I, II,
  and III in its review.
- **No new LLM call site without tracing**: A new LLM invocation MUST emit layer-tagged
  traces (Principle VI) before it is merged.
- **Constitution gate**: Each feature plan's Constitution Check gate verifies adherence to
  these principles before design proceeds; unavoidable deviations are recorded and justified
  in the plan's Complexity Tracking.

## Governance

This constitution supersedes other development practices for this service. When guidance
conflicts, the constitution wins.

- **Amendments**: Proposed changes MUST be documented, reviewed, and approved before adoption,
  and MUST carry a version bump per the policy below.
- **Versioning policy**:
  - **MAJOR**: Removal or backward-incompatible redefinition of a principle or governance rule.
  - **MINOR**: A new principle or section is added, or existing guidance is materially expanded.
  - **PATCH**: Clarifications, wording, or non-semantic refinements.
- **Compliance**: All plans and PRs MUST verify compliance with these principles. Violations
  MUST be justified in the plan's Complexity Tracking or remediated before merge.
- **Runtime guidance**: `CLAUDE.md` provides agent-facing runtime development guidance and
  defers to this constitution on principle questions.

**Version**: 1.1.0 | **Ratified**: 2026-06-11 | **Last Amended**: 2026-06-11
