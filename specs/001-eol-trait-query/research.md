# Phase 0 Research: EOL Trait Query Service

This document resolves the open technical decisions behind the plan. Each entry follows
Decision / Rationale / Alternatives considered. The architecture brief supplied with `/speckit-plan`
fixed most of the hard choices; the work here is selecting concrete mechanisms that honor the
constitution and the upstream constraints.

## R1. Term→URI grounding (the dominant problem)

**Decision**: Resolve user phrasing to ontology URIs by **retrieval over an embedded catalog of
the graph's own terms**, built by enumerating `Term {type:"measurement"}`, `Term {type:"association"}`,
and value terms from EOL itself. `resolve_predicate(text)` returns ranked candidate `Term`s
`{name, uri, type}`; the model never emits a URI directly. The catalog is persisted locally and
rebuildable from the self-describing graph.

**Rationale**: Ontology URIs ("body mass" = `VT_0001259`, "size" = `PATO_0000117`, "eats" =
`RO_0002471`) are exactly what a general model hallucinates. Constitution IV mandates retrieval,
not training; the graph is self-describing so the catalog is authoritative and refreshable. Keeping
URIs out of free generation is also what lets the validator enforce "all URIs resolved" (II).

**Alternatives considered**: (a) Trusting the LLM to recall URIs — rejected, guaranteed
hallucination and unverifiable. (b) Fine-tuning a domain model on EOL terms — rejected per
Constitution IV (opaque, expensive to refresh, couples to model lifecycle). (c) Pure string/fuzzy
matching — kept as a cheap pre-filter and for exact-name hits, but insufficient alone for
paraphrases and synonyms.

## R2. Embedding model + vector index

**Decision**: Use a configurable embeddings model with a **local, persisted vector index**
(e.g., FAISS or `sqlite-vec`) over the term catalog. Default to a hosted embeddings model where
quality matters (Voyage AI is Anthropic's recommended embeddings provider) with a local
`sentence-transformers` model as a self-contained fallback. The index is a build artifact keyed by
catalog version; rebuilds are offline and do not hit EOL at query time.

**Pinned defaults** (override via config): embeddings `voyage-3-large` (Voyage AI's general-purpose
model — confirm the exact current model name against Voyage's docs at integration time, since
Anthropic recommends Voyage but does not enumerate its model catalog), with a local
`sentence-transformers` `all-MiniLM-L6-v2` as the self-contained fallback.

**Rationale**: The catalog is small (10^3–10^5 terms), so a local index gives sub-millisecond
lookups, zero per-query upstream load (Principle VII), and full offline testability. Keeping the
embeddings model behind a thin interface satisfies "domain specificity lives in retrieval" without
hard-coupling to one vendor.

**Alternatives considered**: A managed vector DB (Pinecone/Weaviate) — rejected as operational
overhead unjustified at this catalog size. Embedding at query time without persistence — rejected,
wasteful and slower.

## R3. Service-side LLM + constrained decoding

**Decision**: Use **Mellea constrained decoding** to produce a **format-valid typed intent object**
for the scoped extraction/judgment work, on **Mellea's default local Granite/Ollama backend**.
Semantic correctness comes from the resolve-and-verify step (R1) and the validator — not from the
decoding constraint or the model's domain knowledge.

**Rationale**: Constitution V scopes the service model to extraction, term/taxon resolution, repair,
and ambiguity judgment — a narrow, constrained-decoded task where retrieval (R1) does the domain
grounding. Per the Principle IV scope clarification (constitution v1.1.0), the frontier-LLM
requirement binds the *client orchestrator* and grounding, not this scoped extractor; so the
extractor MAY run on a small, local, constrained model. Mellea's local default (Granite on Ollama)
needs no API key, runs offline, is cheap and low-latency (helps SC-006), and keeps an external
provider off the hot path. Model id/backend is configuration, not load-bearing architecture.

**Pinned default** (override via config): service-side extractor `granite4.1:3b` via Mellea's local
Ollama backend. A general frontier Claude model (e.g. `claude-sonnet-4-6`, `claude-opus-4-8`) is a
drop-in configurable upgrade — recommended for the hard disambiguation/repair tail where a 3B model
may underperform.

**Open spikes before committing the default at scale**: (1) verify Mellea's constrained-decoding
guarantee holds on the Ollama/Granite backend (structured-output fidelity can vary by backend);
(2) measure extraction quality on the ambiguous tail (US-6/US-7 phrasings) at 3B — keep the frontier
escape hatch for cases where it underperforms.

**Alternatives considered**: A general frontier model as the *default* for the extractor — rejected
as the default (adds an API-key dependency and per-call cost to the common path for a task a small
constrained model handles) but retained as a configurable option. Free-form JSON prompting without
constrained decoding — rejected (format drift). A domain-tuned model — rejected per Constitution IV
(domain knowledge lives in retrieval, not weights).

## R4. Two-tier split and where guarantees live

**Decision**: Service-side owns NL→intent, resolution, repair, and the catalog of known shapes; the
**external calling model** owns only the genuinely novel multi-hop long tail, decomposing it into a
chain of **set-valued single-hop** tool calls. All guarantees (validation, versioned shapes, repair
rules) live in-service.

**Rationale**: Constitution III/V. Guarantees must be versioned, testable, and consistent per call,
not re-derived probabilistically by whatever client connects. Handing the rare hardest reasoning to
an external model is a deliberate, accepted trade because novel multi-hop questions are rare.

**Alternatives considered**: Service-side general agent that plans arbitrary multi-hop chains —
rejected per Constitution V ("keep the service model on a short leash"). Client-side resolution —
rejected; it would scatter the guarantees outside the trust boundary.

## R5. The single validator (no bypass)

**Decision**: One `validator/` module with one entry point asserts: (1) an explicit `LIMIT` is
present, (2) every ontology URI referenced is one that resolution produced (no model-invented URIs),
(3) the query is read-only (no `CREATE`/`SET`/`DELETE`/`MERGE`/`REMOVE`/etc.). `run_cypher` refuses
to execute anything that has not returned a positive validator verdict. Both the template path and
the tool path go through `run_cypher`.

**Rationale**: Constitution II. A single choke point is the only place safety can be guaranteed.
Server-side mutation rejection by EOL is treated as defense-in-depth, not our only guard.

**Alternatives considered**: Per-path validation — rejected, multiplies bypass risk. Relying on
EOL's server-side mutation rejection alone — rejected; it does not cover missing `LIMIT` or invented
URIs and gives no local, testable guarantee.

## R6. Upstream client: auth, formats, caching, caps, errors

**Decision**: `upstream/` calls `https://eol.org/service/cypher` with `query` + `format`, attaching
a **single shared admin JWT** (from config/secret, not per-user). Request `format=cypher` (native
neo4j JSON) and **map every result into the service contract** — never pass `cypher`/`csv` through.
Cache the enumerated term lists aggressively with explicit TTL/invalidation. Apply deliberate result
caps and set a `truncated` flag when a cap is hit. Map upstream timeout/error to an explicit
`upstream-unavailable` outcome (FR-013), distinct from `no-records` (FR-010) and internal errors;
bounded retries with backoff, never a tight loop.

**Rationale**: Constitution I (map, don't leak), VII (be gentle, cache, caps, empty-is-valid), and
spec FR-013. Case-sensitivity of URIs is preserved end-to-end (no lower-casing in mappers or
matching).

**Alternatives considered**: Passing neo4j JSON straight through — rejected per Constitution I.
Per-user tokens — rejected; upstream issues one admin JWT. Unbounded results — rejected per VII/SC-005.

## R7. Set-valued single-hop tool and server-side multi-hop

**Decision**: The single-hop tool accepts a **set of `page_id`s and returns sets**; intermediate IDs
move as **structured data**, never round-tripped as prose. Anticipated multi-hop shapes are modeled
as a **parameterized n-hop predicate-chain intent** whose join runs **server-side under a single
`LIMIT`** (the EOL `WITH DISTINCT … carry page forward … match next predicate` skeleton templates
cleanly). Only the unanticipated falls to calling-model decomposition.

**Rationale**: Avoids fan-out into hundreds of single-entity calls and keeps the model context free
of large ID lists. Server-side joins under one `LIMIT` avoid the application-layer chaining hazards.

**Three silent failure modes explicitly guarded** (carried into data-model + tests):
- **Per-hop `LIMIT` truncation** of intermediate sets → surface as `truncated` (SC-005), never silent.
- **Set cardinality** → hop inputs are sets, not single entities; the tool signature enforces this.
- **Direction inversion** across hops → assert relationship direction at every hop (RO_0002471 is
  *eaten by*; trivially invertible into nonsense).

## R8. Deterministic, versioned repair loop

**Decision**: Encode repair as in-service, versioned, testable rules in `repair/`:
- Empty result after a name match → retry with `page_id` (homonym).
- Categorical predicate queried as numeric → read `object_term`, not `normal_measurement`.
- Missing roll-up → add `parent_term|synonym_of*0..`.
- Inverted association direction → flip and re-assert direction.
- Genuinely ambiguous → escalate to scoped-LLM judgment, else to a user clarification (FR-009/US-6).
- Capture repair-loop misses to grow the rule set over time.

**Rationale**: Constitution III — determinism for the known. Repair is rules first, model last; each
rule is independently testable and version-pinned.

**Alternatives considered**: LLM-driven repair as the default — rejected; non-deterministic, untestable.

## R9. Observability

**Decision**: OpenTelemetry tracing where **every span carries a `layer` tag** (`client-orchestrator`
vs `service-extractor`) plus the resolved model id and token/cost counters, from day one. Latency,
cost, and errors are attributable per layer.

**Rationale**: Constitution VI. Two LLM layers make un-attributed telemetry useless; retrofitting
tracing is "tracing never added."

**Alternatives considered**: Logging only — rejected; cannot attribute cost/latency across the two
layers. Deferring tracing to post-MVP — rejected per Constitution VI ("from day one").

## R10. Disambiguation interaction model

**Decision**: Stateless, single-shot (spec FR-014). On low-confidence taxon or predicate resolution,
return a `needs-clarification` result carrying the structured candidate set; the client resubmits
with the chosen identifier. The service holds no multi-turn conversation state.

**Rationale**: Keeps orchestration on the client (Constitution V), keeps the service simple and
horizontally scalable, and makes the disambiguation path directly testable against the labeled
ambiguity set (SC-004, a 100% hard gate).

**Alternatives considered**: Service-held conversational state — rejected; statefulness pushes
orchestration into the scoped service against Constitution V and complicates the SC-004 gate.
