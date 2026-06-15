"""Embedded predicate-term catalog + resolver (T011 — Constitution Principle IV).

Enumerates EOL's predicate terms (``measurement`` + ``association``; ~645) via the live transport,
embeds them once, and persists the matrix; at query time it cosine-ranks the user's phrase against
the matrix to produce ``PredicateCandidate``s carrying **full EOL URIs**. Brute-force numpy over a
few hundred terms is instant, so no vector database is used.

Note (EOL type gap — handled): EOL types both numeric and categorical predicates as
``measurement`` (e.g. ``habitat`` is ``measurement`` though its values are ``object_term``). The
pipeline routes measurement/categorical predicates to the dual-slot ``attribute`` shape, which
reads both value slots and maps whichever is populated — so categorical-valued measurement
predicates answer correctly.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np

from eol_genai_service.contract import PredicateCandidate
from eol_genai_service.resolution.embeddings import Embedder
from eol_genai_service.resolution.predicates import PredicateTerm

Transport = Callable[[str, str], list[dict[str, object]]]

# Predicate terms only (values come back as object_term in results, not resolved from user text).
_ENUMERATE_QUERY = (
    "MATCH (t:Term) WHERE t.type IN ['measurement', 'association'] "
    "RETURN t.uri AS uri, t.name AS name, t.type AS type, t.alias AS alias, "
    "t.definition AS definition LIMIT 5000"
)


def enumerate_predicate_terms(transport: Transport) -> list[PredicateTerm]:
    """Enumerate predicate terms from the self-describing graph (full URIs)."""
    terms: list[PredicateTerm] = []
    for row in transport(_ENUMERATE_QUERY, "cypher"):
        uri = row.get("uri")
        if not uri:
            continue
        alias = row.get("alias") or ""
        terms.append(
            PredicateTerm(
                uri=str(uri),
                name=str(row.get("name") or ""),
                type=str(row.get("type") or ""),
                aliases=(alias,) if alias else (),
            )
        )
    return terms


def _doc_text(term: PredicateTerm) -> str:
    """The text embedded for a catalog term (name + aliases)."""
    parts = [term.name, *term.aliases]
    return ". ".join(p for p in parts if p)


class PredicateEmbeddingIndex:
    """The embedded predicate catalog: terms + a normalized embedding matrix, cosine-searchable."""

    def __init__(self, terms: list[PredicateTerm], matrix: np.ndarray) -> None:
        self._terms = terms
        self._matrix = matrix  # (N, dim), L2-normalized rows

    @classmethod
    def build(cls, terms: list[PredicateTerm], embedder: Embedder) -> "PredicateEmbeddingIndex":
        matrix = embedder.embed_documents([_doc_text(t) for t in terms])
        return cls(terms, matrix)

    def search(self, query_vec: np.ndarray, k: int = 5) -> list[tuple[PredicateTerm, float]]:
        sims = self._matrix @ query_vec  # cosine (both normalized)
        top = np.argsort(sims)[::-1][:k]
        return [(self._terms[i], float(sims[i])) for i in top]

    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "matrix.npy", self._matrix)
        (directory / "terms.json").write_text(
            json.dumps(
                [
                    {"uri": t.uri, "name": t.name, "type": t.type, "aliases": list(t.aliases)}
                    for t in self._terms
                ]
            )
        )

    @classmethod
    def load(cls, directory: str | Path) -> "PredicateEmbeddingIndex":
        directory = Path(directory)
        matrix = np.load(directory / "matrix.npy")
        raw = json.loads((directory / "terms.json").read_text())
        terms = [
            PredicateTerm(uri=t["uri"], name=t["name"], type=t["type"], aliases=tuple(t["aliases"]))
            for t in raw
        ]
        return cls(terms, matrix)


class EmbeddingPredicateResolver:
    """Resolve a predicate phrase to ranked ``PredicateCandidate``s by cosine over the catalog."""

    def __init__(self, index: PredicateEmbeddingIndex, embedder: Embedder, k: int = 5) -> None:
        self._index = index
        self._embedder = embedder
        self._k = k

    def resolve(self, text: str) -> list[PredicateCandidate]:
        query_vec = self._embedder.embed_query(text)
        return [
            PredicateCandidate(uri=term.uri, name=term.name, type=term.type, score=score)
            for term, score in self._index.search(query_vec, self._k)
        ]
