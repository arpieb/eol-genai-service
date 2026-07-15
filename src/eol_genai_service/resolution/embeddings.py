"""Embedding backends for term→URI grounding (T011 — Constitution Principle IV).

The grounding is retrieval, not training. Embeddings run through **litellm**, so the provider is a
config choice (``ollama/<model>`` local by default, or ``voyage/<model>``, ``openai/<model>``, …)
rather than a hardwired SDK — the service never imports a provider package directly. The default is
a local Ollama model (``mxbai-embed-large``): no key, offline, off the per-query hot path.

mxbai is a retrieval model with **asymmetric prompting**: documents (catalog terms) are embedded
plain; queries (user phrases) are embedded with a retrieval prefix (:data:`QUERY_PREFIX`). This
asymmetry is essential — without it the contrast between right and wrong terms nearly vanishes
(verified by spike) — and it is model-specific, so it lives in the embedder, not the call sites.

Vectors are L2-normalized so cosine similarity is a plain dot product. The catalog is tiny (~645
predicate terms), so a brute-force numpy matmul is instant — no vector database needed.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from eol_genai_service.upstream.client import UpstreamUnavailable

# mxbai-embed-large's retrieval query instruction (documents are embedded without it).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalization (zero rows are left as-is)."""
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class LiteLLMEmbedder:
    """Provider-agnostic embedder via litellm. Documents plain; queries with ``query_prefix``.

    ``model`` is a litellm provider-prefixed id (e.g. ``"ollama/mxbai-embed-large"``,
    ``"voyage/voyage-3-large"``). ``query_prefix`` is the model-specific retrieval instruction
    applied to queries only (empty for models that don't use one). ``api_base`` overrides the
    provider endpoint (litellm defaults Ollama to ``http://localhost:11434``).
    """

    def __init__(self, model: str, *, query_prefix: str = "", api_base: str | None = None) -> None:
        self.model = model
        self.query_prefix = query_prefix
        self.api_base = api_base

    def _embed(self, inputs: list[str]) -> np.ndarray:
        import litellm

        kwargs: dict[str, object] = {"model": self.model, "input": inputs}
        if self.api_base is not None:
            kwargs["api_base"] = self.api_base
        try:
            resp = litellm.embedding(**kwargs)
        except Exception as exc:  # noqa: BLE001 - any embedding-backend failure is "unavailable"
            # The embedding backend (Ollama by default) is an upstream dependency: map a
            # connection/timeout/rate-limit/5xx failure to the shared UpstreamUnavailable signal so
            # the pipeline surfaces upstream_unavailable, not an unhandled crash — like the EOL
            # Cypher and taxon-search paths. (litellm's exception base is openai's, which we don't
            # import; matching EolCypherClient's "any backend failure is unavailable" convention.)
            raise UpstreamUnavailable(f"embedding backend unavailable: {exc}") from exc
        # litellm may return data out of order; the `index` field is authoritative.
        rows = sorted(resp["data"], key=lambda d: d["index"])
        return l2_normalize(np.array([r["embedding"] for r in rows], dtype="float32"))

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([self.query_prefix + text])[0]


class FastEmbedEmbedder:
    """In-process embedder via fastembed (ONNX Runtime, CPU) — no server, no network, no API key.

    Runs the embedding model *inside this process*, so a deployment (e.g. the MCP container) is
    self-contained: no Ollama and no hosted embedding API. Same :class:`Embedder` contract as
    :class:`LiteLLMEmbedder` — documents embedded plain, queries with ``query_prefix``, vectors
    L2-normalized so cosine similarity is a plain dot product — so it drops into the resolver
    unchanged and keeps score parity with the tuned confidence gates (use the same model,
    ``mixedbread-ai/mxbai-embed-large-v1``).

    The model (ONNX weights) is loaded lazily on first use, so constructing this is cheap and no
    weights are needed until an ``embed`` call. ``cache_dir`` pins where fastembed stores/loads the
    weights (bake them into the image at build time to avoid a first-run download).
    """

    def __init__(self, model_id: str, *, query_prefix: str = "", cache_dir: str | None = None) -> None:
        self.model_id = model_id
        self.query_prefix = query_prefix
        self.cache_dir = cache_dir
        self._model = None  # lazy — the ONNX model is loaded on first embed()

    def _ensure_model(self):
        if self._model is None:
            # Imported lazily so fastembed is only required when the local backend is actually used.
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_id, cache_dir=self.cache_dir)
        return self._model

    def _embed(self, inputs: list[str]) -> np.ndarray:
        model = self._ensure_model()
        try:
            # fastembed yields one vector per input, in order.
            vectors = list(model.embed(inputs))
        except Exception as exc:  # noqa: BLE001 - any local-model failure is "unavailable"
            # Match the LiteLLMEmbedder convention: map a model/runtime failure to the shared
            # UpstreamUnavailable signal so predicate resolution surfaces upstream_unavailable
            # rather than crashing (Principle II parity across embedding backends).
            raise UpstreamUnavailable(f"embedding backend unavailable: {exc}") from exc
        return l2_normalize(np.array(vectors, dtype="float32"))

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([self.query_prefix + text])[0]
