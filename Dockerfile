# EOL Trait Query Service — HTTP API container.
# Built with uv against the locked dependency set. Run: `docker run -p 8000:8000 --env-file .env <img>`.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    EOL_API_HOST=0.0.0.0 \
    EOL_API_PORT=8000

WORKDIR /app

# Install dependencies first (cached layer) from the lockfile, without the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the package source, and install the project (registers the console scripts).
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8000

# EOL_JWT (+ a reachable Ollama / embedding backend) enables the live stack; without it the API
# serves the offline fixture pipeline. The predicate index persists under .cache/predicate_index.
CMD ["uv", "run", "eol-genai-api"]
