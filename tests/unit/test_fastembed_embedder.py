"""Unit tests for the in-process FastEmbedEmbedder (the model is faked — no weights loaded)."""

import numpy as np
import pytest

from eol_genai_service.config import Settings
from eol_genai_service.factory import build_embedder
from eol_genai_service.resolution.embeddings import (
    QUERY_PREFIX,
    FastEmbedEmbedder,
    LiteLLMEmbedder,
)
from eol_genai_service.upstream.client import UpstreamUnavailable


class _FakeModel:
    """Stands in for fastembed.TextEmbedding: records inputs, yields fixed vectors in order."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, inputs):
        inputs = list(inputs)
        self.calls.append(inputs)
        base = [np.array([3.0, 0.0], dtype="float32"), np.array([0.0, 4.0], dtype="float32")]
        for vec in base[: len(inputs)]:
            yield vec


def test_embed_documents_normalizes_and_preserves_order():
    emb = FastEmbedEmbedder("mixedbread-ai/mxbai-embed-large-v1", query_prefix=QUERY_PREFIX)
    emb._model = _FakeModel()  # inject fake so no ONNX weights are loaded

    out = emb.embed_documents(["a", "b"])

    assert out.shape == (2, 2)
    assert np.allclose(out[0], [1.0, 0.0])  # [3,0] normalized
    assert np.allclose(out[1], [0.0, 1.0])  # [0,4] normalized
    assert emb._model.calls[0] == ["a", "b"]  # documents embedded plain (no prefix)


def test_embed_query_applies_the_retrieval_prefix():
    emb = FastEmbedEmbedder("mixedbread-ai/mxbai-embed-large-v1", query_prefix=QUERY_PREFIX)
    emb._model = _FakeModel()

    vec = emb.embed_query("body mass")

    assert vec.shape == (2,)
    assert emb._model.calls[0] == [QUERY_PREFIX + "body mass"]  # asymmetric prompting


def test_model_failure_maps_to_upstream_unavailable():
    class _Boom:
        def embed(self, inputs):
            raise RuntimeError("onnxruntime blew up")

    emb = FastEmbedEmbedder("x")
    emb._model = _Boom()
    with pytest.raises(UpstreamUnavailable):
        emb.embed_query("body mass")


def test_construction_is_lazy():
    # Constructing must not load the model (weights load on first embed only).
    emb = FastEmbedEmbedder("mixedbread-ai/mxbai-embed-large-v1")
    assert emb._model is None


def test_build_embedder_local_backend_selects_fastembed():
    for backend in ("local", "fastembed"):
        emb = build_embedder(
            Settings(
                embeddings_backend=backend,
                embeddings_model_id="mixedbread-ai/mxbai-embed-large-v1",
            )
        )
        assert isinstance(emb, FastEmbedEmbedder)
        assert emb.model_id == "mixedbread-ai/mxbai-embed-large-v1"
        assert emb.query_prefix == QUERY_PREFIX  # mxbai → retrieval prefix
        assert emb._model is None  # lazy — nothing loaded at build_embedder time


def test_build_embedder_cache_dir_from_env(monkeypatch):
    monkeypatch.setenv("EOL_EMBEDDINGS_CACHE_DIR", "/tmp/fe-cache")
    emb = build_embedder(Settings(embeddings_backend="local", embeddings_model_id="mxbai-x"))
    assert isinstance(emb, FastEmbedEmbedder)
    assert emb.cache_dir == "/tmp/fe-cache"


def test_build_embedder_non_local_still_uses_litellm():
    emb = build_embedder(
        Settings(embeddings_backend="voyage", embeddings_model_id="voyage-3-large")
    )
    assert isinstance(emb, LiteLLMEmbedder)
    assert emb.model == "voyage/voyage-3-large"
