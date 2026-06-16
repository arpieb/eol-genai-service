"""SC-006 latency gate against the LIVE path (live-integration §6). Skipped without EOL_JWT+Ollama.

Measures real end-to-end latency over the live stack — Mellea/Granite extraction + embedding
predicate retrieval + EOL search-API taxon resolution + one upstream Cypher round-trip — for
canonical-shape questions (US-1..US-5), and asserts each shape's **typical** (median over repeats)
warm-cache latency stays within the 5 s budget (SC-006).

Robust to the 2018-era EOL server's real-world variance, two ways:
  - Per-question **medians** ignore a one-off slow call in a question's repeats, while a genuine
    regression — a shape's typical latency climbing toward budget — still fails.
  - Transient upstream errors (search-API rate limit / 5xx) are tolerated: that sample is skipped,
    and if the server rate-limits us hard enough that nothing is measurable the test **skips** rather
    than failing (we can't measure latency when the upstream won't answer). A small inter-call pause
    keeps us gentle on the old server (Principle VII).

Latency is timed only over calls that reach EOL; a reached-EOL floor guards against a false green
(if resolution regressed and every question short-circuited, the timing would look great while
measuring nothing). The offline `test_latency.py` is the CI regression guard; this is the live gate.
"""

import time

import httpx
import pytest

from support import ollama_up
from eol_genai_service.config import Settings, load_env
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.factory import build_deps
from eol_genai_service.orchestration.pipeline import answer

load_env()
_SETTINGS = Settings.from_env()

SC006_BUDGET_SECONDS = 5.0
REPEATS = 3  # per question; the median tolerates a transient EOL spike in any single repeat
_PAUSE_SECONDS = 0.25  # be gentle on the 2018-era server between calls (Principle VII)

# Canonical-shape questions (US-1..US-5) verified to resolve confidently and reach EOL. Scientific
# names are used deliberately: common names ("sea otter") resolve ambiguous on the live search API
# and would short-circuit to needs_clarification before the upstream call (a different, shorter path).
CANONICAL = [
    "what is the body mass of Enhydra lutris?",  # US-1 measurement
    "what is the habitat of Enhydra lutris?",  # US-2 categorical (type-gap)
    "what does Enhydra lutris eat?",  # US-3 association
    "how many taxa have a recorded body mass?",  # US-4 aggregate count
    "what is the ancestry of Enhydra lutris?",  # US-5 lineage
    "what is the body mass of Panthera leo?",  # US-1, second taxon
]


pytestmark = pytest.mark.skipif(
    not (_SETTINGS.eol_jwt and ollama_up()), reason="needs EOL_JWT + Ollama"
)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def test_live_canonical_typical_latency_within_budget(capsys):
    deps = build_deps()  # live stack (EOL_JWT set); predicate index loaded from .cache
    # Warm cache: prime the Mellea session connect + first upstream round-trip outside timing.
    answer(AnswerRequest(question=CANONICAL[0]), deps)

    medians: dict[str, float] = {}
    reached = total = errors = 0
    for q in CANONICAL:
        eol_samples: list[float] = []
        for _ in range(REPEATS):
            start = time.perf_counter()
            try:
                result = answer(AnswerRequest(question=q), deps)
            except httpx.HTTPError:
                # Transient upstream (search-API rate limit / 5xx) — skip this sample, stay gentle.
                errors += 1
                time.sleep(_PAUSE_SECONDS)
                continue
            elapsed = time.perf_counter() - start
            total += 1
            if result.outcome in ("answer", "no_records"):  # timed only over real EOL round-trips
                reached += 1
                eol_samples.append(elapsed)
            time.sleep(_PAUSE_SECONDS)
        if eol_samples:
            medians[q] = _median(eol_samples)

    worst = max(medians.values()) if medians else float("inf")
    with capsys.disabled():
        print(
            f"\nSC-006 live: reached_eol={reached}/{total} upstream_errors={errors} "
            f"worst_typical={worst:.2f}s"
        )
        for q, m in medians.items():
            print(f"  median {m:5.2f}s  {q}")

    # If the upstream rate-limited / errored so hard we measured nothing, skip — we can't gate latency
    # when the server won't answer (this is not a latency regression).
    if not medians:
        pytest.skip(f"could not measure live latency: {errors} transient upstream errors")

    # False-green guard: most non-erroring calls must reach EOL, not short-circuit before the round-trip.
    assert reached >= total // 2, f"only {reached}/{total} reached EOL"
    assert worst <= SC006_BUDGET_SECONDS, (
        f"slowest typical (median) latency {worst:.2f}s exceeds {SC006_BUDGET_SECONDS}s budget"
    )
