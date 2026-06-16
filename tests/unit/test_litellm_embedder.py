"""Unit tests for the provider-agnostic LiteLLMEmbedder (litellm calls are mocked)."""

import litellm
import numpy as np

from eol_genai_service.config import Settings
from eol_genai_service.factory import build_embedder
from eol_genai_service.resolution.embeddings import QUERY_PREFIX, LiteLLMEmbedder


def _fake_embedding(record: dict):
    def _embedding(model, input, **kwargs):
        record["model"] = model
        record["input"] = list(input)
        record["kwargs"] = kwargs
        # Return rows out of order to prove the embedder sorts by `index`.
        return {
            "data": [
                {"index": i, "embedding": vec}
                for i, vec in reversed(list(enumerate([[3.0, 0.0], [0.0, 4.0]][: len(input)])))
            ]
        }

    return _embedding


def test_embed_documents_normalizes_and_orders_by_index(monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(litellm, "embedding", _fake_embedding(rec))
    emb = LiteLLMEmbedder("ollama/mxbai-embed-large", query_prefix=QUERY_PREFIX)

    out = emb.embed_documents(["a", "b"])

    assert out.shape == (2, 2)
    assert np.allclose(out[0], [1.0, 0.0])  # index 0 → [3,0] normalized
    assert np.allclose(out[1], [0.0, 1.0])  # index 1 → [0,4] normalized
    assert rec["model"] == "ollama/mxbai-embed-large"
    assert rec["input"] == ["a", "b"]  # documents are embedded plain (no prefix)


def test_embed_query_applies_the_retrieval_prefix(monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(litellm, "embedding", _fake_embedding(rec))
    emb = LiteLLMEmbedder("ollama/mxbai-embed-large", query_prefix=QUERY_PREFIX)

    vec = emb.embed_query("body mass")

    assert vec.shape == (2,)
    assert rec["input"] == [QUERY_PREFIX + "body mass"]  # asymmetric prompting


def test_api_base_forwarded_only_when_set(monkeypatch):
    rec: dict = {}
    monkeypatch.setattr(litellm, "embedding", _fake_embedding(rec))
    LiteLLMEmbedder("ollama/x", api_base="http://host:11434").embed_documents(["a"])
    assert rec["kwargs"].get("api_base") == "http://host:11434"

    rec.clear()
    monkeypatch.setattr(litellm, "embedding", _fake_embedding(rec))
    LiteLLMEmbedder("ollama/x").embed_documents(["a"])
    assert "api_base" not in rec["kwargs"]  # let litellm use its provider default


def test_build_embedder_maps_config_to_litellm_model_and_prefix():
    # Default (mxbai on ollama) → ollama-prefixed model + the mxbai retrieval prefix.
    default = build_embedder(Settings())
    assert isinstance(default, LiteLLMEmbedder)
    assert default.model == "ollama/mxbai-embed-large"
    assert default.query_prefix == QUERY_PREFIX

    # A non-mxbai provider (Voyage) → provider-prefixed model, no retrieval prefix.
    voyage = build_embedder(
        Settings(embeddings_backend="voyage", embeddings_model_id="voyage-3-large")
    )
    assert voyage.model == "voyage/voyage-3-large"
    assert voyage.query_prefix == ""
