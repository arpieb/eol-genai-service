"""SC-001 accuracy gate over recorded real-EOL data (live-integration §6).

Deterministic CI gate: replays the captured golden set (scientific-name questions covering the
canonical shapes US-1..US-5) through the **full pipeline** — extract → resolve → validate →
run_cypher (recorded) → map — and asserts the answer matches hand-written-query ground truth at the
SC-001 target (≥90%). Ground truth + cassettes are captured live by `scripts/record_sc001_golden.py`
(`golden.json` + `golden_transport.json`); re-run it when shapes change.

This gate verifies **pipeline correctness over real EOL data** (right shape, right URI, right mapped
value, for all five shapes). The complementary **live recall** stress-test — does Granite + the
embedding resolver actually ground each question — is measured by the same capture script and was
100% on this set; it is non-deterministic, so it is not a committed CI assertion.
"""

from eol_genai_service.config import Settings
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.extraction.extract import RuleBasedExtractor
from eol_genai_service.orchestration.pipeline import PipelineDeps, answer
from eol_genai_service.resolution.predicates import CatalogPredicateResolver, PredicateTerm
from eol_genai_service.upstream.client import EolCypherClient
from support import (
    BODY_MASS,
    EATS,
    HABITAT,
    load_cassette,
    recorded_search_resolver,
    replay_transport,
)

_GOLDEN = load_cassette("golden.json")
_TRANSPORT = load_cassette("golden_transport.json")
_SEARCH = load_cassette("search.json")

SC001_TARGET = 0.90

# Extractor/resolver vocabulary: surface aliases for each predicate URI captured from live EOL. The
# URIs and types themselves come from golden.json (not duplicated here) — these only map user phrasing
# to the captured URI so the offline RuleBasedExtractor + CatalogPredicateResolver stand in for the
# live Granite + embedding grounding (which the capture script measures separately).
_PRED_ALIASES = {
    BODY_MASS: ("body mass", "mass", "weight", "how heavy"),
    HABITAT: ("habitat", "lives in", "biome"),
    EATS: ("eat", "eats", "diet", "preys on"),
}


def _predicate_catalog() -> list[PredicateTerm]:
    seen: dict[str, PredicateTerm] = {}
    for entry in _GOLDEN:
        p = entry["predicate"]
        if p and p["uri"] in _PRED_ALIASES and p["uri"] not in seen:
            seen[p["uri"]] = PredicateTerm(
                uri=p["uri"], name=p["name"], type=p["type"], aliases=_PRED_ALIASES[p["uri"]]
            )
    return list(seen.values())


def _recorded_deps() -> PipelineDeps:
    pred_forms = {a for aliases in _PRED_ALIASES.values() for a in aliases}
    taxon_forms = {e["scientific_name"].lower() for e in _GOLDEN if e["scientific_name"]}
    settings = Settings()  # result_cap=100 matches the cap the cassettes were captured at
    return PipelineDeps(
        extractor=RuleBasedExtractor(pred_forms, taxon_forms),
        predicate_resolver=CatalogPredicateResolver(_predicate_catalog()),
        taxon_resolver=recorded_search_resolver(_SEARCH),
        client=EolCypherClient(settings, replay_transport(_TRANSPORT)),
        settings=settings,
    )


def _matches(result, expected: dict) -> bool:
    """Strict: the answer must reproduce the captured shape, URI, count, and mapped value."""
    if result.outcome != expected["outcome"]:
        return False
    if result.outcome != "answer":
        return True
    if expected.get("count_nonnegative"):
        return result.count is not None and result.count >= 0
    if not result.statements:
        return False
    s = result.statements[0]
    if s.value.kind != expected["kind"] or s.predicate.uri != expected["predicate_uri"]:
        return False
    if len(result.statements) != expected["n_statements"]:
        return False
    if expected["kind"] == "quantitative":
        return s.value.amount == expected["amount"]
    if expected["kind"] == "categorical":
        return s.value.term.name == expected["term_name"]
    if expected["kind"] == "taxon":
        return s.value.direction == expected["direction"]
    return True


def test_sc001_accuracy_over_recorded_eol_meets_target():
    deps = _recorded_deps()
    results = [
        (e, _matches(answer(AnswerRequest(question=e["question"]), deps), e["expected"]))
        for e in _GOLDEN
    ]
    correct = sum(ok for _, ok in results)
    accuracy = correct / len(results)
    misses = [e["question"] for e, ok in results if not ok]
    assert accuracy >= SC001_TARGET, f"{correct}/{len(results)} = {accuracy:.0%}; missed: {misses}"


def test_golden_set_covers_all_canonical_shapes():
    # SC-001 is over US-1..US-5; make sure the golden set actually spans them.
    assert {e["shape"] for e in _GOLDEN} == {
        "measurement",
        "categorical",
        "association",
        "count",
        "lineage",
    }
