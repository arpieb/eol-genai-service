"""The MCP composition root defaults embeddings to the in-process (local) backend."""

from types import SimpleNamespace

from eol_genai_service import factory
from eol_genai_service.tools import server


def _stub_build_deps(seen):
    def _fake(settings):
        seen["backend"] = settings.embeddings_backend
        seen["model"] = settings.embeddings_model_id
        return SimpleNamespace(predicate_resolver=SimpleNamespace(catalog=lambda: []))

    return _fake


def test_build_live_surface_defaults_to_local(monkeypatch):
    # Isolate from the real .env and any inherited value.
    monkeypatch.setattr("eol_genai_service.config.load_env", lambda: None)
    monkeypatch.delenv("EOL_EMBEDDINGS_BACKEND", raising=False)
    monkeypatch.delenv("EOL_EMBEDDINGS_MODEL_ID", raising=False)
    seen: dict = {}
    monkeypatch.setattr(factory, "build_deps", _stub_build_deps(seen))

    server.build_live_surface()

    assert seen["backend"] == "local"
    assert seen["model"] == "mixedbread-ai/mxbai-embed-large-v1"


def test_explicit_backend_overrides_the_mcp_default(monkeypatch):
    monkeypatch.setattr("eol_genai_service.config.load_env", lambda: None)
    monkeypatch.setenv("EOL_EMBEDDINGS_BACKEND", "voyage")
    monkeypatch.setenv("EOL_EMBEDDINGS_MODEL_ID", "voyage-3-large")
    seen: dict = {}
    monkeypatch.setattr(factory, "build_deps", _stub_build_deps(seen))

    server.build_live_surface()

    assert seen["backend"] == "voyage"  # real env wins over the setdefault
    assert seen["model"] == "voyage-3-large"
