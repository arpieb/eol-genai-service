"""Embedding backends for term→URI grounding (T011 — Constitution Principle IV).

The grounding is retrieval, not training. The default embedder is a local Ollama model
(``mxbai-embed-large``) — no key, offline, off the per-query hot path. mxbai is a retrieval model
with **asymmetric prompting**: documents (catalog terms) are embedded plain; queries (user phrases)
are embedded with a retrieval prefix. This asymmetry is essential — without it the contrast between
right and wrong terms nearly vanishes (verified by spike).

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


class OllamaEmbedder:
    """Embeds via a local Ollama model. Documents plain; queries with the retrieval prefix."""

    def __init__(self, model_id: str = "mxbai-embed-large") -> None:
        self._model = model_id

    def _embed(self, inputs: list[str]) -> np.ndarray:
        import ollama

        resp = ollama.embed(model=self._model, input=inputs)
        return l2_normalize(np.array(resp["embeddings"], dtype="float32"))

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([QUERY_PREFIX + text])[0]
