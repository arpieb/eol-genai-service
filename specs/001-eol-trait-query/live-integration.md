# Live Integration Checklist

Wires the live backends in behind the protocol seams already built for the offline fixture build.
Maps the remaining tasks (**T002, T003, T011, T014**) plus the deferred live EOL transport onto
concrete steps. The pipeline, contract, validator, shapes, mappers, and repair rules are
**unchanged** — only the backends behind the seams get swapped.

**Critical-path order**: §2 (live EOL transport) → §3 (term catalog; needs EOL + Voyage) →
§4 (Mellea; needs Ollama) → §5/§6. §2 alone makes every existing shape run against real EOL with
the offline extractor/resolvers as a useful intermediate milestone.

## 0. Prerequisites / secrets

- [ ] **EOL JWT** from the EOL maintainer → set `EOL_JWT` (never commit; `.env*` is `.gitignore`'d).
- [ ] `EOL_CYPHER_URL` confirmed (`https://eol.org/service/cypher`).
- [ ] **Ollama** running with **two models pulled**: `granite4.1:3b` (service extractor) and
  `mxbai-embed-large` (embeddings) — `ollama pull granite4.1:3b && ollama pull mxbai-embed-large`.
  Both defaults are local: no Anthropic or Voyage key needed for the common path.
- [ ] *(Optional upgrades)* Frontier extractor backend → `EOL_SERVICE_MODEL_BACKEND=anthropic` +
  `ANTHROPIC_API_KEY`; hosted embeddings → `EOL_EMBEDDINGS_BACKEND=voyage` + Voyage key in
  `EMBEDDINGS_API_KEY`.

## 1. Dependencies (T002 / T003)

- [ ] `uv add mellea anthropic opentelemetry-sdk opentelemetry-api mcp` (T002).
- [ ] `uv add ollama` (local embeddings + Granite via the Ollama client) and a vector index
  `faiss-cpu` **or** `sqlite-vec` (T003, per research R2). `uv add voyageai` only if enabling the
  hosted-embeddings upgrade.
- [ ] `uv sync` green; CI lockfile check (`uv sync --locked`) still passes.

## 2. Live EOL transport (deferred half of T008) — unblocks everything ✅ DONE

- [x] **httpx-backed `Transport`** — `upstream/http_transport.py` (`HttpEolTransport`): GET with
  `query`+`format`, `Authorization: JWT <token>` header (verified live), parses neo4j
  `{columns, data}` → row dicts, raises on timeout/HTTP error (→ `UpstreamUnavailable`).
- [x] **Composition root** — `eol_genai_service/factory.py` (`build_deps`): live transport when
  `EOL_JWT` is set, else fixture transport; wired into `api/app.py` (prod ASGI `app`; `create_app`
  still defaults to offline so tests never hit the network).
- [x] **Verified live**: a real query returns parsed rows; an empty match → `[]` (→ `no_records`),
  not an error (`tests/integration/test_eol_live.py`, skipif no `EOL_JWT`).
- [ ] **Gate (blocked on T011)**: one real query per canonical shape end-to-end. The live branch
  still uses the fixture-catalog resolvers, whose page_ids/URIs don't match real EOL, so live
  queries currently return `no_records`. Completing this needs the EOL-enumerated catalog (T011)
  + the full-URI fix recorded in §3.

## 3. Embedded term catalog + retrieval resolvers (T011)

> **Finding (§2 probe) — EOL stores FULL URIs.** Terms are stored as e.g.
> `http://purl.obolibrary.org/obo/VT_0001259` (body mass), `http://eol.org/schema/terms/...`, not
> the short `VT_0001259` the fixtures use. So T011 must: (a) enumerate/resolve to **full** URIs;
> (b) **widen the validator URI regex** (`validator/core.py` currently matches `[A-Z]+_[0-9]+`) to
> match full `http(s)://…` URI literals and compare them whole against the resolved set (preserving
> SC-002); (c) update the shape templates' `{uri:'…'}` interpolation accordingly. Re-run the
> SC-002/SC-003 validator tests after the regex change.

- [ ] **Enumerate** predicate/value `Term`s from the self-describing graph
  (`Term {type:"measurement"}`, `{type:"association"}`, value terms) via the live transport.
- [ ] **Embed** with the configured embeddings backend (default: local `mxbai-embed-large` on
  Ollama); persist a local vector index (FAISS/sqlite-vec), keyed by catalog **and embedding-model**
  version. Wire it behind the existing **`CatalogIndex`** cache (`resolution/index.py` — TTL/rebuild
  already done). Catalog and query embeddings MUST use the same model; a model change forces a
  `CatalogIndex.rebuild()`.
- [ ] **Spike — embeddings recall@k bake-off** (research R2): embeddings are load-bearing
  (drive SC-001/SC-004), so measure the rank of the correct ontology URI for paraphrased/synonym
  queries on a labeled term set, **local `mxbai-embed-large` vs Voyage `voyage-3-large`**. Keep the
  local default if it clears the bar; otherwise flip `EOL_EMBEDDINGS_BACKEND=voyage` for the hard
  grounding tail.
- [ ] Implement **embedding-backed `PredicateResolver`/`TaxonResolver`** (replacing `Catalog*Resolver`)
  returning the same `PredicateCandidate`/`TaxonCandidate` shapes + scores. `resolve_taxon` prefers
  EOL page/search lookup (FR-003).
- [ ] **Re-tune** `CONFIDENCE_THRESHOLD` / `AMBIGUITY_MARGIN` in `pipeline.py` against real embedding
  score distributions (they were set for the deterministic fixtures).
- [ ] **Gate**: SC-002 holds — every URI the resolver emits is catalog-real; the validator rejects
  anything else (already enforced).

## 4. Mellea extractor on local Granite (T014)

- [ ] Implement `MelleaExtractor` behind the existing **`Extractor`** protocol
  (`extraction/extract.py`): NL → `QueryIntent` via Mellea constrained decoding on the
  Ollama/Granite backend (`service_model_backend="ollama"`, `service_model_id="granite4.1:3b"`).
- [ ] **Spike 1** (research R3): confirm Mellea's **constrained-decoding guarantee holds on the
  Ollama/Granite backend** — the typed `QueryIntent` must always parse. If weak, fall back to the
  Anthropic backend or add a parse-retry.
- [ ] **Spike 2**: measure **extraction quality on the ambiguous tail** (US-6/US-7 phrasings) at 3B;
  keep `EOL_SERVICE_MODEL_BACKEND=anthropic` as the configurable escape hatch for the hard cases.
- [ ] Keep `RuleBasedExtractor` as the offline/CI default (so CI stays key-free).
- [ ] **Gate**: the extractor emits *raw surface phrases* (not pre-resolved entities) so
  disambiguation stays owned by resolution (the US-6 invariant).

## 5. Observability exporter (Principle VI)

- [ ] Wire an **OpenTelemetry exporter** behind the `span()` `sink` seam (`observability/tracing.py`);
  tag every LLM call site with its `Layer` + `model_id` + tokens/cost.
- [ ] **Gate**: a real request's trace attributes latency/cost to `service-extractor` vs
  `client-orchestrator` (the `totals_by_layer` test already asserts the shape).

## 6. Verification — make the SC gates real

- [x] **SC-001**: golden set is scientific-name questions covering US-1..US-5, ground truth captured
  from live EOL by `scripts/record_sc001_golden.py` into `golden.json` + `golden_transport.json`.
  `tests/integration/test_accuracy_recorded.py` replays it through the full pipeline (deterministic,
  CI-safe) and asserts ≥90% — **passing at 100%** (right shape/URI/value for all five shapes).
  The complementary **live recall** stress-test (Granite extract + embedding grounding + EOL) over 3
  repeats/question measured **100% (18/18)** end-to-end; it's non-deterministic so it stays in the
  capture script, not a committed assertion. Common names are deliberately excluded (they resolve
  ambiguous on the live search API → `needs_clarification`); the offline `test_accuracy_golden.py`
  remains a fast synthetic smoke check.
- [x] **SC-006**: `tests/integration/test_latency_live.py` measures the live path (Mellea/Granite
  extract + embedding retrieve + EOL search-API taxon resolution + one upstream Cypher) for canonical
  US-1..US-5 questions, skip-guarded on `EOL_JWT`+Ollama. **Measured warm-cache p95 ≈ 0.63 s** (max
  0.63 s, mean 0.53 s over 18 samples) — well within the 5 s budget. Caveats: cold first call ~4.4 s
  (one-time Mellea session connect); the EOL **search API can spike** (~6 s observed for some taxa)
  and common names resolve ambiguous → `needs_clarification` before the upstream call, so the gate
  uses scientific names and a reached-EOL floor to measure the real answer path.
- [x] **Recorded fixtures for CI**: `scripts/record_eol_cassettes.py` captures real EOL responses
  to `tests/fixtures/eol_cassettes/`; `tests/integration/test_eol_recorded.py` replays them (no
  skipif) so the EOL-facing pipeline — validator (full URIs), attribute shape, neo4j→contract
  mapping, search-API taxon resolver — runs in **CI with no JWT/network**, against real data.
- [x] **Recorded full-`answer()` (U1)**: `tests/integration/test_recorded_answer.py` routes a
  natural question through the *entire* pipeline (extract → resolve → validate → run_cypher[recorded]
  → map → `AnswerResult`) over the recorded transport, asserting the contract outcome carries the
  real recorded value/provenance — both the quantitative (body mass 5525) and categorical type-gap
  (habitat "marine benthic") paths. Closes the gap where only the EOL-facing layers, not `answer()`
  itself, were exercised against real recorded rows.
- [x] SC-002/SC-003 (validator) pass structurally; the type-gap/categorical and search paths now
  also run against recorded real EOL rows in CI. (The Mellea/embeddings paths still need a local
  model, so those live tests remain skip-only.)

## 7. Rollout / governance

- [ ] **Respect the upstream** (Principle VII): term-list cache warm before load; deliberate result
  caps; bounded retry on EOL.
- [ ] Constitution re-check (v1.1.0): frontier model only for client orchestration / hard tail;
  service extractor on local Granite by default.
- [ ] Update `README.md` "Live integration" section with the verified run recipe; flip the status
  table from "offline fixtures" to "live".

## Seam reference (what swaps where)

| Live backend | Seam (already in place) | Task |
|--------------|-------------------------|------|
| httpx EOL client | `Transport` callable on `EolCypherClient` | T008 (deferred half) |
| Embedded term catalog | `CatalogIndex` (`resolution/index.py`) | T011 |
| Embedding resolvers | `PredicateResolver` / `TaxonResolver` protocols | T011 |
| Mellea extractor | `Extractor` protocol (`extraction/extract.py`) | T014 |
| OTel exporter | `span(..., sink=...)` (`observability/tracing.py`) | — |
| Composition root | `PipelineDeps` (offline `build_offline_deps` is the template) | — |
