# EOL Trait Query Service

Answer natural-language biodiversity questions against the Encyclopedia of Life (EOL) trait graph,
returning correct, sourced, **structured** results. Clients never write or see Cypher.

See [`specs/001-eol-trait-query/`](specs/001-eol-trait-query/) for the governing spec, plan,
research, data model, contracts, and the project [constitution](.specify/memory/constitution.md).

## Status

All eight user stories (US-1 through US-8) are implemented and run **end-to-end against offline
fixtures** — no network, JWT, LLM, or embeddings required. Live integrations (real EOL endpoint,
Mellea-constrained extractor, Voyage embeddings) sit behind protocol seams and are pending API
keys (tasks T002/T003/T011/T014).

| Capability | Story | Outcome |
|------------|-------|---------|
| Single fact (e.g. body mass) | US-1 | quantitative value + provenance |
| Categorical attribute (habitat) | US-2 | controlled term + provenance |
| Ecological association (eats) | US-3 | partner taxon, correct direction |
| Aggregate count (with roll-up) | US-4 | rolled-up count |
| Lineage | US-5 | ordered ancestor chain |
| Disambiguation | US-6 | `needs_clarification` (never a guess) |
| No data | US-8 | explicit `no_records` |
| Novel multi-hop | US-7 | composed via tool surface, or `out_of_capability` |

## Tooling

- Package/env manager: **`uv`** (do not use `pip`/`venv` directly).
- Python: **3.14+** (pinned by `.python-version`).

## Run

```bash
uv sync                                          # provision .venv from pyproject + uv.lock
uv run uvicorn eol_genai_service.api.app:app --reload   # serve POST /v1/answer (offline fixtures)
```

Ask a question:

```bash
curl -s localhost:8000/v1/answer -H 'content-type: application/json' \
  -d '{"question": "how heavy is a sea otter?"}'
# → {"outcome":"answer","statements":[{"value":{"kind":"quantitative","amount":25.0,"units":"kg",...}}],...}
```

The endpoint always returns one of five outcomes: `answer`, `no_records`, `needs_clarification`,
`upstream_unavailable`, `out_of_capability` (see
[`contracts/client-contract.md`](specs/001-eol-trait-query/contracts/client-contract.md)).

## Test, lint, format

```bash
uv run pytest                  # full suite (offline)
uv run ruff check src tests    # lint
uv run ruff format src tests   # format
```

Success-criteria gates are enforced by the suite: validator hard gates (SC-002/SC-003), the
SC-001 accuracy harness, the SC-004 ambiguity gate, SC-005 truncation, and the SC-006 latency
check.

## Architecture (one paragraph)

Two-tier with a single hard validator between everything and EOL. The **service** owns NL→intent
extraction, term/taxon resolution (retrieval, not training), deterministic versioned query shapes,
and the repair loop; the **calling model** orchestrates the rare novel long tail via a read-only,
set-valued [tool surface](src/eol_genai_service/tools/surface.py). Every query — template or
LLM-generated — reaches EOL only through the
[validator](src/eol_genai_service/validator/core.py) (`LIMIT` present, all URIs resolved,
read-only). The query language and EOL schema never cross the client boundary.

## Live integration (pending keys)

```bash
export EOL_JWT=...                # shared admin token (request from the EOL maintainer)
export EOL_CYPHER_URL=https://eol.org/service/cypher
# embeddings + service model selection via EOL_EMBEDDINGS_MODEL_ID / EOL_SERVICE_MODEL_ID
```

Wire an httpx-backed transport + the embedded term catalog and Mellea extractor at the
composition root; the pipeline is unchanged.
