"""Endpoint overrides for the two model backends (EOL_*_API_BASE).

The embedding provider and the generation backend both default to localhost; these settings are what
lets an operator point them elsewhere (a non-localhost Ollama, a LiteLLM/OpenAI-compatible gateway,
self-hosted vLLM) without code changes. Unset must stay a true no-op so each provider keeps its own
default.
"""

import mellea
import pytest

from eol_genai_service.config import Settings
from eol_genai_service.extraction.mellea_extractor import MelleaExtractor
from eol_genai_service.factory import build_embedder
from eol_genai_service.resolution.embeddings import FastEmbedEmbedder, LiteLLMEmbedder

_ENV_VARS = ("EOL_EMBEDDINGS_API_BASE", "EOL_SERVICE_MODEL_API_BASE")


def test_from_env_reads_both_overrides(monkeypatch):
    monkeypatch.setenv("EOL_EMBEDDINGS_API_BASE", "http://ollama:11434")
    monkeypatch.setenv("EOL_SERVICE_MODEL_API_BASE", "http://gateway:4000")

    settings = Settings.from_env()

    assert settings.embeddings_api_base == "http://ollama:11434"
    assert settings.service_model_api_base == "http://gateway:4000"


@pytest.mark.parametrize("value", [None, ""])
def test_unset_or_blank_means_provider_default(monkeypatch, value):
    # A blank line in .env must read as "use the provider default", not an unusable empty endpoint.
    for name in _ENV_VARS:
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    settings = Settings.from_env()

    assert settings.embeddings_api_base is None
    assert settings.service_model_api_base is None


def test_build_embedder_forwards_api_base():
    emb = build_embedder(
        Settings(
            embeddings_backend="ollama",
            embeddings_model_id="mxbai-embed-large",
            embeddings_api_base="http://ollama:11434",
        )
    )
    assert isinstance(emb, LiteLLMEmbedder)
    assert emb.api_base == "http://ollama:11434"


def test_build_embedder_omits_api_base_by_default():
    emb = build_embedder(Settings())
    assert isinstance(emb, LiteLLMEmbedder)
    assert emb.api_base is None  # LiteLLMEmbedder then omits the kwarg entirely


def test_local_backend_ignores_api_base():
    # fastembed runs the model in this process — there is no endpoint to point at.
    emb = build_embedder(
        Settings(
            embeddings_backend="local",
            embeddings_model_id="mixedbread-ai/mxbai-embed-large-v1",
            embeddings_api_base="http://ignored:11434",
        )
    )
    assert isinstance(emb, FastEmbedEmbedder)


def test_extractor_passes_no_endpoint_kwargs_when_unset():
    # Not the same as base_url=None: mellea's litellm backend defaults base_url to a hardcoded
    # localhost, and its ollama backend lets None fall through to OLLAMA_HOST.
    assert MelleaExtractor(Settings())._endpoint_kwargs() == {}


def test_extractor_passes_base_url_for_constructor_backends():
    for backend in ("ollama", "openai"):
        extractor = MelleaExtractor(
            Settings(service_model_backend=backend, service_model_api_base="http://ollama:11434")
        )
        assert extractor._endpoint_kwargs() == {"base_url": "http://ollama:11434"}


def test_extractor_routes_endpoint_through_model_options_for_litellm_backend():
    # Mellea's LiteLLMBackend accepts base_url but never forwards it to litellm.acompletion, so the
    # endpoint has to ride in model_options, which litellm passes through.
    extractor = MelleaExtractor(
        Settings(
            service_model_backend="litellm",
            service_model_id="anthropic/claude-sonnet-5-5",
            service_model_api_base="http://gateway:4000",
        )
    )
    assert extractor._endpoint_kwargs() == {"model_options": {"api_base": "http://gateway:4000"}}


def test_session_is_started_with_the_endpoint_kwargs(monkeypatch):
    rec: dict = {}

    def fake_start_session(**kwargs):
        rec.update(kwargs)
        return object()

    monkeypatch.setattr(mellea, "start_session", fake_start_session)
    extractor = MelleaExtractor(
        Settings(service_model_api_base="http://ollama:11434")  # ollama backend by default
    )

    extractor._ensure_session()

    assert rec == {
        "backend_name": "ollama",
        "model_id": "granite4.1:3b",
        "base_url": "http://ollama:11434",
    }
