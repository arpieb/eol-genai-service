# EOL Trait Query Service — streamable-http MCP server container.
# Serves the read-only MCP tool surface at /mcp over the modern streamable-http transport,
# so networked agent clients can connect. Build:  docker build -f Dockerfile.mcp -t eol-mcp .
# Run:  docker run -p 8765:8765 --env-file .env eol-mcp
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    EOL_MCP_TRANSPORT=streamable-http \
    EOL_MCP_HOST=0.0.0.0 \
    EOL_MCP_PORT=8765 \
    # In-process embedding model (fastembed / ONNX, CPU) — no Ollama, no hosted API, no key.
    # This is the MCP server's default; the weights are baked in below and loaded from the cache.
    EOL_EMBEDDINGS_BACKEND=local \
    EOL_EMBEDDINGS_MODEL_ID=mixedbread-ai/mxbai-embed-large-v1 \
    EOL_EMBEDDINGS_CACHE_DIR=/app/.cache/fastembed

WORKDIR /app

# Install dependencies first (cached layer) from the lockfile, without the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the package source, and install the project (registers the console scripts).
COPY src ./src
RUN uv sync --frozen --no-dev

# Pre-download the embedding model at build time so the container needs NO network for embeddings
# at startup and cold starts are fast (the ONNX weights bake into this image layer, under the same
# cache dir the app reads at runtime). Requires network during build only.
RUN uv run python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='mixedbread-ai/mxbai-embed-large-v1', cache_dir='/app/.cache/fastembed')"

# Documents the default port. Hosts that inject $PORT (Cloud Run, Render, …) override it below;
# the streamable-http endpoint is served at /mcp (set EOL_MCP_PATH to change).
EXPOSE 8765

# EOL_JWT enables the live stack (Cypher + the startup predicate-index enumeration); without it the
# tools serve the offline fixture surface. Embeddings run in-process (above), so no embedding host
# is required — the only external dependency is EOL itself. The predicate index persists under
# .cache/predicate_index.
#
# JSON (exec) form so SIGTERM reaches the server for a graceful shutdown. `sh -c … exec` still lets
# ${PORT} expand at container start — PaaS platforms that inject $PORT bind it; everything else
# falls back to EOL_MCP_PORT (8765) — while `exec` replaces the shell so signals aren't swallowed.
# Sessions are held in-process, so run a SINGLE instance (or enable sticky sessions) unless you
# switch FastMCP to stateless_http.
CMD ["sh", "-c", "EOL_MCP_PORT=\"${PORT:-$EOL_MCP_PORT}\" exec uv run eol-genai-mcp"]
