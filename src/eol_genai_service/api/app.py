"""FastAPI app exposing the client contract (T017 / T023).

``POST /v1/answer`` takes a natural-language question and returns one of the five contract
outcomes (contracts/client-contract.md). Cypher and EOL internals never cross this boundary
(Constitution Principle I). The app is wired to the offline-fixture pipeline by default; the live
composition root injects real dependencies via :func:`create_app`.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI
from opentelemetry.trace import Tracer

from eol_genai_service.contract import AnswerRequest, Result
from eol_genai_service.factory import build_deps
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.observability import Span
from eol_genai_service.observability.otel import export_spans
from eol_genai_service.orchestration.pipeline import PipelineDeps, answer


def create_app(deps: PipelineDeps | None = None, tracer: Tracer | None = None) -> FastAPI:
    """Build the app. ``deps`` defaults to the **offline** fixture pipeline so tests/dev never hit
    the network; the live ASGI app below injects live deps via :func:`build_deps`.

    When ``tracer`` is provided, each request collects its layer-tagged spans and exports them to
    OpenTelemetry (Principle VI); when None, the request path is unchanged (spans still emit to the
    trace logger). The composition root chooses the exporter — see ``observability.otel``."""
    deps = deps or build_offline_deps()
    app = FastAPI(title="EOL Trait Query Service", version="0.1.0")

    @app.post("/v1/answer", response_model=Result)
    def post_answer(request: AnswerRequest) -> Result:
        if tracer is None:
            return answer(request, deps)
        sink: list[Span] = []
        result = answer(request, replace(deps, span_sink=sink))
        export_spans(tracer, sink)
        return result

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


# Production ASGI entrypoint (`uvicorn eol_genai_service.api.app:app`): live transport when
# EOL_JWT is configured (via .env or the environment), else the offline fixture pipeline.
app = create_app(build_deps())


def serve() -> None:
    """Console entrypoint (``eol-genai-api``): run the HTTP API with uvicorn.

    Host/port come from ``EOL_API_HOST`` / ``EOL_API_PORT`` (default ``0.0.0.0:8000``).
    """
    import os

    import uvicorn

    from eol_genai_service.config import load_env

    load_env()  # ensure .env serving knobs are loaded, not just relied on via import side effects
    uvicorn.run(
        app,
        host=os.getenv("EOL_API_HOST", "0.0.0.0"),
        port=int(os.getenv("EOL_API_PORT", "8000")),
    )
