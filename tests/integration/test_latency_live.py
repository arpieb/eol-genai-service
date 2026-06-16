"""SC-006 latency gate against the LIVE path (live-integration §6). Skipped without EOL_JWT+Ollama.

Measures real end-to-end latency over the live stack — Mellea/Granite extraction + embedding
predicate retrieval + EOL search-API taxon resolution + one upstream Cypher round-trip — for
canonical-shape questions (US-1..US-5), and asserts the warm-cache p95 ≤ 5 s (SC-006).

The offline `test_latency.py` is the CI regression guard; this is the real-dependency gate. It is
gentle on the 2018-era EOL server: the predicate index is loaded once, one warmup call primes the
Mellea session, and only a few iterations run. A reached-EOL floor guards against a false green —
if resolution regressed and every question short-circuited before the upstream call, the p95 would
look great while measuring nothing.
"""

import time
import urllib.request

import pytest

from eol_genai_service.config import Settings, load_env
from eol_genai_service.contract import AnswerRequest
from eol_genai_service.factory import build_deps
from eol_genai_service.orchestration.pipeline import answer

load_env()
_SETTINGS = Settings.from_env()

SC006_P95_SECONDS = 5.0
ITERATIONS = 3

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


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_SETTINGS.eol_jwt and _ollama_up()), reason="needs EOL_JWT + Ollama"
)


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return ordered[idx]


def test_live_canonical_p95_latency_within_budget(capsys):
    deps = build_deps()  # live stack (EOL_JWT set); predicate index loaded from .cache
    # Warm cache: prime the Mellea session connect + first upstream round-trip outside timing.
    answer(AnswerRequest(question=CANONICAL[0]), deps)

    latencies: list[float] = []
    reached = 0
    for _ in range(ITERATIONS):
        for q in CANONICAL:
            start = time.perf_counter()
            result = answer(AnswerRequest(question=q), deps)
            latencies.append(time.perf_counter() - start)
            if result.outcome in ("answer", "no_records"):
                reached += 1

    p95 = _p95(latencies)
    with capsys.disabled():
        print(
            f"\nSC-006 live: n={len(latencies)} reached_eol={reached}/{len(latencies)} "
            f"p95={p95:.2f}s max={max(latencies):.2f}s mean={sum(latencies) / len(latencies):.2f}s"
        )

    # Guard against a false green: if resolution regressed and everything short-circuited before the
    # upstream call, p95 would look great while measuring the wrong (shorter) path.
    assert reached >= len(latencies) // 2, f"only {reached}/{len(latencies)} reached EOL"
    assert p95 <= SC006_P95_SECONDS, f"live p95 {p95:.2f}s exceeds {SC006_P95_SECONDS}s budget"
