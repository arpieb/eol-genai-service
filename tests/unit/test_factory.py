"""Composition-root selection (§2/T011): live stack iff EOL_JWT, offline otherwise."""

import json

import numpy as np

from eol_genai_service import factory
from eol_genai_service.config import Settings
from eol_genai_service.resolution.predicate_index import EmbeddingPredicateResolver
from eol_genai_service.resolution.taxon_search import SearchApiTaxonResolver
from eol_genai_service.upstream.http_transport import HttpEolTransport


def test_build_deps_offline_without_jwt():
    deps = build = factory.build_deps(Settings(eol_jwt=None))
    assert not isinstance(build.client._transport, HttpEolTransport)
    assert deps.settings.resolution_confidence_threshold == 0.85  # offline gates unchanged


def test_build_deps_live_with_jwt(tmp_path, monkeypatch):
    # Seed a tiny on-disk index so the live branch loads instead of enumerating over the network.
    np.save(tmp_path / "matrix.npy", np.zeros((1, 4), dtype="float32"))
    (tmp_path / "terms.json").write_text(
        json.dumps(
            [
                {
                    "uri": "http://x/obo/VT_1",
                    "name": "body mass",
                    "type": "measurement",
                    "aliases": [],
                }
            ]
        )
    )
    monkeypatch.setattr(factory, "_INDEX_DIR", tmp_path)

    deps = factory.build_deps(Settings(eol_jwt="token"))
    assert isinstance(deps.client._transport, HttpEolTransport)
    assert isinstance(deps.predicate_resolver, EmbeddingPredicateResolver)
    assert isinstance(deps.taxon_resolver, SearchApiTaxonResolver)
    # Live path lowers the resolution gates for embedding cosine scores.
    assert deps.settings.resolution_confidence_threshold == 0.5
    assert deps.settings.resolution_ambiguity_margin == 0.05
