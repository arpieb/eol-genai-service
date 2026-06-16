"""Capture the SC-001 golden set from live EOL+Ollama (live-integration §6).

Two jobs, one live pass (run locally with EOL_JWT set + Ollama up):
  1. Record the real EOL I/O (search + Cypher) for a scientific-name golden set covering the
     canonical shapes (US-1..US-5), plus per-question ground truth, into the cassettes +
     golden.json — so `tests/integration/test_accuracy_recorded.py` runs the SC-001 accuracy gate
     deterministically in CI.
  2. Measure the **live** end-to-end accuracy (Granite extract + embedding grounding + EOL) over N
     repeats, which is the real recall stress-test the recorded gate can't do.

Usage: ``uv run python scripts/record_sc001_golden.py``
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from eol_genai_service.config import Settings, load_env
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.factory import build_deps
from eol_genai_service.orchestration.pipeline import answer

_OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eol_cassettes"
_ACCURACY_REPEATS = 3

# Scientific-name golden set covering US-1..US-5. (question, shape, taxon scientific name | None)
GOLDEN = [
    ("what is the body mass of Enhydra lutris?", "measurement", "Enhydra lutris"),
    ("what is the habitat of Enhydra lutris?", "categorical", "Enhydra lutris"),
    ("what does Enhydra lutris eat?", "association", "Enhydra lutris"),
    ("how many taxa have a recorded body mass?", "count", None),
    ("what is the ancestry of Enhydra lutris?", "lineage", "Enhydra lutris"),
    ("what is the body mass of Panthera leo?", "measurement", "Panthera leo"),
]


def _norm(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _expected(result) -> dict:
    """The assertable ground-truth summary for a live answer (shape-specific)."""
    out: dict = {"outcome": result.outcome}
    if result.outcome != "answer":
        return out
    if result.count is not None and not result.statements:
        out["count_nonnegative"] = result.count >= 0
        return out
    s = result.statements[0]
    out["kind"] = s.value.kind
    out["predicate_uri"] = s.predicate.uri
    if s.value.kind == "quantitative":
        out["amount"] = s.value.amount
    elif s.value.kind == "categorical":
        out["term_name"] = s.value.term.name
    elif s.value.kind == "taxon":
        out["partner"] = s.value.taxon.scientific_name
        out["direction"] = s.value.direction
    out["n_statements"] = len(result.statements)
    return out


def _matches(result, expected: dict) -> bool:
    """Did a live run reproduce the captured ground truth (grounding succeeded)?"""
    if result.outcome != expected["outcome"]:
        return False
    if result.outcome != "answer":
        return True
    if "count_nonnegative" in expected:
        return result.count is not None and result.count >= 0
    if not result.statements:
        return False
    s = result.statements[0]
    if s.value.kind != expected.get("kind"):
        return False
    return s.predicate.uri == expected.get("predicate_uri")


def main() -> None:
    load_env()
    if not Settings.from_env().eol_jwt:
        raise SystemExit("EOL_JWT not set — cannot record. Set it in .env.")
    deps = build_deps()

    # Wrap the EOL transport to capture every (query -> rows) the pipeline issues.
    real_transport = deps.client._transport
    transport_cassette: dict[str, list] = {}

    def recording(query: str, fmt: str):
        rows = real_transport(query, fmt)
        transport_cassette[_norm(query)] = rows
        return rows

    deps.client._transport = recording

    # Warm cache (Mellea session connect + first upstream round-trip).
    answer(AnswerRequest(question=GOLDEN[0][0]), deps)

    golden: list[dict] = []
    print("=== capture pass ===")
    for question, shape, sci_name in GOLDEN:
        result = answer(AnswerRequest(question=question), deps)
        expected = _expected(result)
        # Parse the (page_id, uri) the pipeline actually used from the last captured query.
        page_id = pred_uri = pred_type = pred_name = None
        if result.outcome == "answer" and result.statements:
            p = result.statements[0].predicate
            pred_uri, pred_type, pred_name = p.uri, p.type, p.name
            page_id = result.statements[0].subject.page_id
        golden.append(
            {
                "question": question,
                "shape": shape,
                "scientific_name": sci_name,
                "page_id": page_id,
                "predicate": (
                    {"uri": pred_uri, "name": pred_name, "type": pred_type} if pred_uri else None
                ),
                "expected": expected,
            }
        )
        print(f"  {shape:11} {result.outcome:20} <- {question}")

    # Separate cassette so we never clobber transport.json (used by the other recorded tests).
    (_OUT / "golden_transport.json").write_text(json.dumps(transport_cassette, indent=1))
    (_OUT / "golden.json").write_text(json.dumps(golden, indent=1))

    # Record search responses for the distinct scientific names (taxon resolution).
    search: dict[str, dict] = {}
    if (_OUT / "search.json").exists():
        search = json.loads((_OUT / "search.json").read_text())
    for name in {sci for _, _, sci in GOLDEN if sci}:
        resp = httpx.get(
            "https://eol.org/api/search/1.0.json", params={"q": name, "page": 1}, timeout=40
        )
        search[name.lower()] = resp.json()
    (_OUT / "search.json").write_text(json.dumps(search, indent=1))
    print(f"recorded {len(transport_cassette)} transport queries, {len(search)} search names")

    # === live accuracy (the real recall stress-test) ===
    print(f"\n=== live accuracy: {_ACCURACY_REPEATS} repeats/question ===")
    correct = total = 0
    for entry in golden:
        hits = 0
        for _ in range(_ACCURACY_REPEATS):
            r = answer(AnswerRequest(question=entry["question"]), deps)
            ok = _matches(r, entry["expected"])
            hits += ok
            total += 1
            correct += ok
        print(f"  {hits}/{_ACCURACY_REPEATS}  {entry['question']}")
    print(f"\nLIVE end-to-end accuracy: {correct}/{total} = {correct / total:.0%}")


if __name__ == "__main__":
    main()
