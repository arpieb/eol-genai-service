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

## 2. Live EOL transport (deferred half of T008) — unblocks everything

- [ ] Implement an **httpx-backed `Transport`** (`upstream/client.py` or `upstream/http_transport.py`):
  attaches the JWT header, sends `query` + `format=cypher`, applies `upstream_timeout_seconds`,
  raises on timeout/5xx (→ `UpstreamUnavailable`).
- [ ] Add a **composition root** (e.g. `eol_genai_service/factory.py`, wired in `api/app.py`) that
  builds `PipelineDeps` with the real transport when `EOL_JWT` is set, else the fixture transport.
- [ ] **Verify**: URI case-sensitivity preserved end-to-end (no lower-casing); empty result →
  `no_records`, not error.
- [ ] **Gate**: one real query per canonical shape returns rows the existing mappers map cleanly
  (provenance fields present).

## 3. Embedded term catalog + retrieval resolvers (T011)

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

- [ ] **SC-001**: replace the golden set in `test_accuracy_golden.py` with **hand-written EOL
  queries** as ground truth; confirm ≥90% on the live held-out set.
- [ ] **SC-006**: re-run the latency check against the live path (Ollama extract + Voyage retrieve +
  one upstream query); confirm **p95 ≤ 5 s** warm-cache.
- [ ] **Record fixtures for CI**: capture real EOL responses (VCR-style) so `uv run pytest` stays
  **offline and green** in CI — never hit live EOL or burn keys in CI.
- [ ] SC-002/SC-003/SC-004/SC-005 already pass structurally; re-run against recorded fixtures.

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
