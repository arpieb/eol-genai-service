# EOL Trait Query Service

Answer natural-language biodiversity questions against the Encyclopedia of Life (EOL) trait graph,
returning correct, sourced, **structured** results. Clients never write or see Cypher.

See [`specs/001-eol-trait-query/`](specs/001-eol-trait-query/) for the governing spec, plan,
research, data model, contracts, and the project [constitution](.specify/memory/constitution.md).

## Status

All eight user stories (US-1 through US-8) are implemented, and the live stack is wired and
validated against real EOL + a local Ollama: the success-criteria gates pass (SC-001 accuracy 100%
on the canonical golden set; SC-006 warm p95 ≈ 0.6 s). With no `EOL_JWT`/Ollama the service runs the
**offline fixture pipeline** (no network, JWT, LLM, or embeddings) — the default for tests/dev.

| Capability | Story | Outcome |
|------------|-------|---------|
| Single fact (e.g. body mass) | US-1 | quantitative value + provenance |
| Categorical attribute (habitat) | US-2 | controlled term + provenance |
| Ecological association (eats) | US-3 | partner taxon, correct direction |
| Aggregate count (with roll-up) | US-4 | rolled-up count |
| Lineage | US-5 | ordered ancestor chain |
| Disambiguation | US-6 | `needs_clarification` (never a guess) |
| No data | US-8 | explicit `no_records` |
| Novel multi-hop | US-7 | composed via the MCP tool surface, or `out_of_capability` |

## Tooling

- Package/env manager: **`uv`** (do not use `pip`/`venv` directly).
- Python: **3.14+** (pinned by `.python-version`).

## Run

```bash
uv sync                  # provision .venv from pyproject + uv.lock
uv run eol-genai-api     # serve the HTTP API on 0.0.0.0:8000 (EOL_API_HOST/EOL_API_PORT to override)
```

Ask a question:

```bash
curl -s localhost:8000/v1/answer -H 'content-type: application/json' \
  -d '{"question": "how heavy is a sea otter?"}'
# → {"outcome":"answer","statements":[{"value":{"kind":"quantitative","amount":...,"units":...}}],...}
```

The endpoint always returns one of five outcomes — `answer`, `no_records`, `needs_clarification`,
`upstream_unavailable`, `out_of_capability` (see
[`contracts/client-contract.md`](specs/001-eol-trait-query/contracts/client-contract.md)).
`GET /healthz` is a liveness probe.

### MCP tool surface (US-7)

The read-only tool surface the calling model uses to orchestrate novel multi-hop questions is an MCP
server exposing `resolve_predicate`/`resolve_taxon`/`list_predicates`/`get_schema`/`run_cypher`/
`single_hop`/`n_hop_chain` (read-only; every call validator-gated). The transport is selectable via
`EOL_MCP_TRANSPORT`:

```bash
uv run eol-genai-mcp                                  # stdio (default) — local subprocess clients
EOL_MCP_TRANSPORT=streamable-http uv run eol-genai-mcp  # HTTP — serves the standard MCP endpoint at
                                                      # http://EOL_MCP_HOST:EOL_MCP_PORT/mcp (default :8765)
```

Use **stdio** for local clients that spawn the process (e.g. an MCP `command` config); use
**streamable-http** for networked clients that connect to the `/mcp` endpoint (`sse` is the legacy
HTTP transport).

### Docker

```bash
docker build -t eol-genai-service .
docker run -p 8000:8000 --env-file .env eol-genai-service   # serves the API
```

## Configuration

Copy `.env.example` to `.env` and set what you need (all optional — absent values fall back to the
offline pipeline / local defaults):

```bash
EOL_JWT=...                       # shared admin token (request from the EOL maintainer); enables live EOL
EOL_CYPHER_URL=https://eol.org/service/cypher
EOL_EMBEDDINGS_BACKEND=ollama     # litellm provider prefix; local (in-process) | ollama | voyage | …
EOL_EMBEDDINGS_MODEL_ID=mxbai-embed-large
EOL_EMBEDDINGS_API_BASE=          # optional endpoint override; unset = the provider's default
EOL_SERVICE_MODEL_BACKEND=ollama  # mellea backend; ollama | openai | litellm | hf | watsonx
EOL_SERVICE_MODEL_ID=granite4.1:3b
EOL_SERVICE_MODEL_API_BASE=       # optional endpoint override; unset = the backend's default
```

Embeddings route through **litellm** and generation through **mellea**, so the provider is a config
choice — the service imports no provider SDK directly. The local default needs a running Ollama with
`granite4.1:3b` and `mxbai-embed-large` pulled.

The two `*_API_BASE` values point a backend somewhere other than its default `localhost` — a
non-localhost Ollama (including Ollama on the host from inside a container), a LiteLLM or
OpenAI-compatible gateway, or self-hosted vLLM. Leave them unset to keep each provider's own
default; `EOL_EMBEDDINGS_API_BASE` has no effect on the in-process `local` embedding backend.

Hosted generation providers are reached *through* mellea's litellm backend, not as backend names of
their own: a frontier model is `EOL_SERVICE_MODEL_BACKEND=litellm` with
`EOL_SERVICE_MODEL_ID=anthropic/claude-sonnet-5-5` (plus `ANTHROPIC_API_KEY`).

## Test, lint, format

```bash
uv run pytest                  # full suite (offline; live tests skip without EOL_JWT + Ollama)
uv run ruff check src tests    # lint
uv run ruff format src tests   # format
```

## Architecture (one paragraph)

Two-tier with a single hard validator between everything and EOL. The **service** owns NL→intent
extraction (mellea), term/taxon resolution (retrieval over EOL's term tables, not training), and
deterministic versioned query shapes; the **calling model** orchestrates the rare novel long tail
via a read-only, set-valued [tool surface](src/eol_genai_service/tools/surface.py) exposed over MCP.
Every query — template or LLM-composed — reaches EOL only through the
[validator](src/eol_genai_service/validator/core.py) (`LIMIT` present, all URIs resolved,
read-only). The query language and EOL schema never cross the client boundary.
