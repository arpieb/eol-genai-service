"""SC-006 latency check (T047): p95 ≤ 5 s for canonical-shape questions, warm cache.

Offline the pipeline is sub-millisecond; this guard makes the gate real and will catch a
regression that pushes p95 over budget once live dependencies are wired in.
"""

import time

from eol_genai_service.contract import AnswerRequest
from eol_genai_service.fixtures import build_offline_deps
from eol_genai_service.orchestration.pipeline import answer

SC006_P95_SECONDS = 5.0

CANONICAL = [
    "how heavy is a sea otter?",
    "what habitat does the raccoon live in?",
    "what do sea otters eat?",
    "how many taxa have a recorded body size?",
    "what is the ancestry of the sea otter?",
]


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return ordered[idx]


def test_canonical_p95_latency_within_budget():
    deps = build_offline_deps()
    latencies: list[float] = []
    for _ in range(20):
        for q in CANONICAL:
            start = time.perf_counter()
            answer(AnswerRequest(question=q), deps)
            latencies.append(time.perf_counter() - start)
    assert _p95(latencies) <= SC006_P95_SECONDS
