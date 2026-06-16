"""U1: the **full** `answer()` pipeline over recorded real-EOL data (live-integration §6).

The recorded-EOL test (`test_eol_recorded.py`) replays real EOL rows through the EOL-facing layers
by hand-calling the shape builder + mapper. This test closes the remaining gap: it routes a natural
question through the *entire* pipeline — extract → resolve predicate → resolve taxon → validate →
run_cypher (recorded transport) → map → `AnswerResult` — and asserts the contract outcome carries
the real recorded values. No JWT, no network, no LLM, no embeddings.

The predicate/taxon resolvers are seeded with the **real EOL grounding values** (full ontology URIs
and the cassette's page ids) so the pipeline builds exactly the queries the transport recorded; the
embedding/search resolvers have their own dedicated tests. The recorded cassette is keyed by page
id, so the seeded taxa use synthetic surface forms (``specimen a/b``) — the assertions check the
recorded measurement/category values and provenance, not taxonomic identity.
"""

import json
import re
from pathlib import Path

from eol_genai_service.config import Settings
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.extraction.extract import RuleBasedExtractor
from eol_genai_service.orchestration.pipeline import PipelineDeps, answer
from eol_genai_service.repair.capture import MissCapture
from eol_genai_service.resolution.predicates import CatalogPredicateResolver, PredicateTerm
from eol_genai_service.resolution.taxa import CatalogTaxonResolver, TaxonRecord
from eol_genai_service.upstream.client import EolCypherClient

_CASSETTES = Path(__file__).resolve().parent.parent / "fixtures" / "eol_cassettes"
_TRANSPORT = json.loads((_CASSETTES / "transport.json").read_text())

_BODY_MASS = "http://purl.obolibrary.org/obo/VT_0001259"
_HABITAT = "http://rs.tdwg.org/dwc/terms/habitat"

# Real EOL grounding values (full URIs); habitat is measurement-typed in EOL though its value is
# categorical (the type-gap path the dual-slot attribute shape handles).
_PREDICATES = [
    PredicateTerm(
        uri=_BODY_MASS,
        name="body mass",
        type="measurement",
        aliases=("body mass", "how heavy", "heavy", "weigh", "mass", "weight"),
    ),
    PredicateTerm(
        uri=_HABITAT,
        name="habitat",
        type="measurement",
        aliases=("habitat", "lives in", "live", "where does", "biome", "environment"),
    ),
]
# The cassette is keyed by page id (Page nodes carry no scientific name), so these are synthetic
# surface forms that resolve to the recorded pages.
_TAXA = [
    TaxonRecord(page_id=328598, scientific_name="Specimen A", vernaculars=("specimen a",)),
    TaxonRecord(page_id=47098272, scientific_name="Specimen B", vernaculars=("specimen b",)),
]


def _norm(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _replay_transport(query: str, fmt: str) -> list[dict]:
    """Return the recorded rows for a query (KeyError if the pipeline built an unrecorded query)."""
    return _TRANSPORT[_norm(query)]


def _recorded_deps(miss_capture: MissCapture | None = None) -> PipelineDeps:
    # result_cap=5 so the built query matches the recorded transport key (recorded at cap 5).
    settings = Settings(result_cap=5)
    pred_forms = {f for t in _PREDICATES for f in (t.name.lower(), *(a.lower() for a in t.aliases))}
    taxon_forms = {f for t in _TAXA for f in (t.scientific_name.lower(), *t.vernaculars)}
    return PipelineDeps(
        extractor=RuleBasedExtractor(pred_forms, taxon_forms),
        predicate_resolver=CatalogPredicateResolver(_PREDICATES),
        taxon_resolver=CatalogTaxonResolver(_TAXA),
        client=EolCypherClient(settings, _replay_transport),
        settings=settings,
        miss_capture=miss_capture,
    )


def test_full_answer_quantitative_from_recorded_eol():
    capture = MissCapture()
    result = answer(AnswerRequest(question="how heavy is specimen a?"), _recorded_deps(capture))

    assert result.outcome == "answer"
    assert result.cap == 5
    stmt = result.statements[0]
    assert stmt.subject.page_id == 328598  # the page the pipeline resolved + queried
    assert stmt.predicate.uri == _BODY_MASS
    assert stmt.value.kind == "quantitative"
    assert stmt.value.amount == 5525.0  # real recorded EOL value
    assert stmt.provenance.resource["name"] == "Smith et al 2011"
    assert len(capture) == 0  # a successful answer is not a capability gap


def test_full_answer_categorical_type_gap_from_recorded_eol():
    # habitat is measurement-typed but carries an object_term value; the dual-slot attribute shape
    # must surface the category, not no_records.
    result = answer(AnswerRequest(question="where does specimen b live?"), _recorded_deps())

    assert result.outcome == "answer"
    stmt = result.statements[0]
    assert stmt.subject.page_id == 47098272
    assert stmt.value.kind == "categorical"
    assert stmt.value.term.name == "marine benthic"  # real recorded EOL value
