"""FastAPI app exposing the client contract (T017 / T023).

``POST /v1/answer`` takes a natural-language question and returns one of the five contract
outcomes (contracts/client-contract.md). Cypher and EOL internals never cross this boundary
(Constitution Principle I). The app is wired to the offline-fixture pipeline by default; the live
composition root injects real dependencies via :func:`create_app`.
"""

from __future__ import annotations

from fastapi import FastAPI

from eol_genai_service.contract import AnswerRequest, Result
from eol_genai_service.factory import build_deps
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import PipelineDeps, answer


def create_app(deps: PipelineDeps | None = None) -> FastAPI:
    """Build the app. ``deps`` defaults to the **offline** fixture pipeline so tests/dev never hit
    the network; the live ASGI app below injects live deps via :func:`build_deps`."""
    deps = deps or build_offline_deps()
    app = FastAPI(title="EOL Trait Query Service", version="0.1.0")

    @app.post("/v1/answer", response_model=Result)
    def post_answer(request: AnswerRequest) -> Result:
        return answer(request, deps)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


# Production ASGI entrypoint (`uvicorn eol_genai_service.api.app:app`): live transport when
# EOL_JWT is configured (via .env or the environment), else the offline fixture pipeline.
app = create_app(build_deps())
