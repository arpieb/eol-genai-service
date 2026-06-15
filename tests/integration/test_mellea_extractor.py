"""Live Mellea extractor tests (T014) — run only when Ollama is reachable.

These exercise the real `granite4.1:3b` model via Mellea's constrained decoding. They are skipped
automatically when Ollama is not up (so CI stays offline/key-free and green; the offline
RuleBasedExtractor remains the default everywhere else). Spike 1 (constrained decoding always
parses) and Spike 2 (canonical-shape quality) are the assertions below.
"""

import urllib.request

import pytest

from eol_genai_service.config import Settings
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.extraction.mellea_extractor import MelleaExtractor
from eol_genai_service.fixtures import (
    PREDICATE_CATALOG,
    TAXON_CATALOG,
    fixture_transport,
)
from eol_genai_service.orchestration.pipeline import PipelineDeps, answer
from eol_genai_service.resolution.predicates import CatalogPredicateResolver
from eol_genai_service.resolution.taxa import CatalogTaxonResolver
from eol_genai_service.upstream.client import EolCypherClient


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ollama_up(), reason="Ollama not reachable on :11434")


@pytest.fixture(scope="module")
def extractor() -> MelleaExtractor:
    return MelleaExtractor()  # defaults to ollama / granite4.1:3b per Settings


@pytest.mark.parametrize(
    "question,expected_shape,expected_taxon",
    [
        ("how heavy is a sea otter?", "single_fact", "sea otter"),
        ("what habitat does the raccoon live in?", "categorical_attribute", "raccoon"),
        ("what do sea otters eat?", "association", "sea otter"),
        ("what is the ancestry of the sea otter?", "lineage", "sea otter"),
    ],
)
def test_canonical_shapes_extract_correctly(extractor, question, expected_shape, expected_taxon):
    intent = extractor.extract(question)
    assert intent.shape == expected_shape, intent
    assert any(expected_taxon in t.lower() for t in intent.taxon_refs), intent


def test_count_question_is_aggregate_count_with_rollup(extractor):
    intent = extractor.extract("how many taxa have a recorded body size?")
    assert intent.shape == "aggregate_count"
    assert intent.rollup is True
    assert intent.taxon_refs == ()  # a count is not about one named taxon


def test_constrained_decoding_always_parses(extractor):
    # Spike 1: every output is a format-valid QueryIntent (no parse exceptions leak).
    for q in ["how heavy is a sea otter?", "asdf qwerty?", "what is the meaning of life?"]:
        intent = extractor.extract(q)
        assert intent.shape in {
            "single_fact",
            "categorical_attribute",
            "association",
            "aggregate_count",
            "lineage",
            "n_hop_chain",
            "novel",
        }


def test_live_extractor_drops_into_pipeline_with_offline_resolvers(extractor):
    # End-to-end: the live Mellea extractor + offline fixture resolvers/transport → a real answer,
    # proving the protocol seam (no pipeline change).
    settings = Settings()
    deps = PipelineDeps(
        extractor=extractor,
        predicate_resolver=CatalogPredicateResolver(PREDICATE_CATALOG),
        taxon_resolver=CatalogTaxonResolver(TAXON_CATALOG),
        client=EolCypherClient(settings, fixture_transport),
        settings=settings,
    )
    result = answer(AnswerRequest(question="how heavy is a sea otter?"), deps)
    # The seam works if a valid contract Result flows through. A live 3B model varies its
    # extraction run-to-run (e.g. taxon "otter" → needs_clarification, or a synonym predicate),
    # so we don't hard-assert "answer"; when it does extract cleanly, the value must be correct.
    assert result.outcome in {
        "answer",
        "needs_clarification",
        "no_records",
        "out_of_capability",
    }
    if result.outcome == "answer":
        assert result.statements[0].value.amount == 25.0
        assert result.statements[0].value.units == "kg"
