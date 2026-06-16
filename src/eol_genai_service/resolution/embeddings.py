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
        resp = litellm.embedding(**kwargs)
        # litellm may return data out of order; the `index` field is authoritative.
        rows = sorted(resp["data"], key=lambda d: d["index"])
        return l2_normalize(np.array([r["embedding"] for r in rows], dtype="float32"))

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([self.query_prefix + text])[0]
