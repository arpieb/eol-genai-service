"""T002b: the FastAPI request path exports layer-tagged spans to OTel when a tracer is injected."""

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from eol_genai_service.api.app import create_app
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.observability.otel import build_tracer_provider, get_tracer


def _client_with_inmemory_otel():
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(exporter)
    app = create_app(build_offline_deps(), tracer=get_tracer(provider))
    return TestClient(app), exporter


def test_request_exports_extract_and_run_cypher_spans_tagged_by_layer():
    client, exporter = _client_with_inmemory_otel()
    resp = client.post("/v1/answer", json={"question": "how heavy is a sea otter?"})
    assert resp.status_code == 200

    finished = exporter.get_finished_spans()
    names = {s.name for s in finished}
    assert {"extract", "run_cypher"} <= names
    # Every exported span is attributed to a reasoning layer (Principle VI).
    assert all(s.attributes["layer"] == "service-extractor" for s in finished)
    extract = next(s for s in finished if s.name == "extract")
    assert extract.attributes["model_id"] == "granite4.1:3b"


def test_request_path_unchanged_without_a_tracer():
    # Default (no tracer): the endpoint still answers; no export machinery is engaged.
    client = TestClient(create_app(build_offline_deps()))
    resp = client.post("/v1/answer", json={"question": "how heavy is a sea otter?"})
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "answer"
