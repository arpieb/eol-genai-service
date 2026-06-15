"""Offline tests for the embedded predicate catalog (T011) — fake embedder, no Ollama/EOL."""

import numpy as np

from eol_genai_service.resolution.embeddings import l2_normalize
from eol_genai_service.resolution.predicate_index import (
    EmbeddingPredicateResolver,
    PredicateEmbeddingIndex,
    enumerate_predicate_terms,
)
from eol_genai_service.resolution.predicates import PredicateTerm

_BODY_MASS = "http://purl.obolibrary.org/obo/VT_0001259"
_HABITAT = "http://rs.tdwg.org/dwc/terms/habitat"
_EATS = "http://purl.obolibrary.org/obo/RO_0002470"


class BowEmbedder:
    """Deterministic bag-of-words embedder over a fixed vocab (cosine = word overlap)."""

    def __init__(self, vocab: list[str]) -> None:
        self._vocab = vocab

    def _vec(self, text: str) -> np.ndarray:
        words = set(text.lower().replace(".", " ").split())
        return np.array([1.0 if w in words else 0.0 for w in self._vocab], dtype="float32")

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return l2_normalize(np.vstack([self._vec(t) for t in texts]))

    def embed_query(self, text: str) -> np.ndarray:
        return l2_normalize(self._vec(text)[None, :])[0]


_VOCAB = ["body", "mass", "habitat", "eats", "heavy"]
_TERMS = [
    PredicateTerm(uri=_BODY_MASS, name="body mass", type="measurement", aliases=()),
    PredicateTerm(uri=_HABITAT, name="habitat", type="measurement", aliases=()),
    PredicateTerm(uri=_EATS, name="eats", type="association", aliases=()),
]


def test_enumerate_predicate_terms_maps_full_uris_and_types():
    def fake_transport(query, fmt):
        assert "measurement" in query and "association" in query
        return [
            {"uri": _BODY_MASS, "name": "body mass", "type": "measurement", "alias": ""},
            {"uri": _HABITAT, "name": "habitat", "type": "measurement", "alias": "habitat"},
            {"uri": _EATS, "name": "eats", "type": "association", "alias": ""},
            {"uri": None, "name": "skip me", "type": "measurement"},  # no uri → skipped
        ]

    terms = enumerate_predicate_terms(fake_transport)
    assert [t.uri for t in terms] == [_BODY_MASS, _HABITAT, _EATS]
    assert {t.type for t in terms} == {"measurement", "association"}
    assert terms[1].aliases == ("habitat",)


def test_resolver_ranks_correct_term_top_with_full_uri():
    emb = BowEmbedder(_VOCAB)
    resolver = EmbeddingPredicateResolver(PredicateEmbeddingIndex.build(_TERMS, emb), emb, k=3)
    cands = resolver.resolve("heavy mass")  # overlaps "mass" in body mass
    assert cands[0].uri == _BODY_MASS
    assert cands[0].uri.startswith("http://")  # full URI, not short form
    assert cands[0].score > cands[1].score


def test_index_save_load_round_trip(tmp_path):
    emb = BowEmbedder(_VOCAB)
    index = PredicateEmbeddingIndex.build(_TERMS, emb)
    index.save(tmp_path)
    reloaded = PredicateEmbeddingIndex.load(tmp_path)
    top = reloaded.search(emb.embed_query("mass"), k=1)[0]
    assert top[0].uri == _BODY_MASS
