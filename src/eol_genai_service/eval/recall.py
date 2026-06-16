"""Recall@k / MRR for predicate resolution (research R2 bake-off).

Backend-agnostic: pass any ``resolve(text) -> [candidate(uri, score)]`` and a labeled set of
``(query phrase, expected term URI)``. Reports recall@1/@3/@5 and mean reciprocal rank, plus the
score of the correct candidate (to tune the confidence gate). Runs against whichever embedder the
config selects (local Ollama by default); point the embeddings config at another provider to compare.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

# A resolver returns ranked candidates exposing .uri and .score.
Resolve = Callable[[str], Sequence[object]]


@dataclass(frozen=True)
class RecallMetrics:
    n: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    mean_correct_score: float  # avg score of the correct candidate when found (gate tuning)
    misses: tuple[str, ...]  # queries where the expected URI was not in the ranked list

    def summary(self) -> str:
        return (
            f"n={self.n} R@1={self.recall_at_1:.0%} R@3={self.recall_at_3:.0%} "
            f"R@5={self.recall_at_5:.0%} MRR={self.mrr:.2f} "
            f"mean_correct_score={self.mean_correct_score:.2f}"
        )


def evaluate(resolve: Resolve, labeled: Sequence[tuple[str, str]]) -> RecallMetrics:
    """Evaluate ``resolve`` over ``labeled`` = [(query, expected_uri), ...]."""
    n = h1 = h3 = h5 = 0
    rr = 0.0
    correct_scores: list[float] = []
    misses: list[str] = []
    for query, expected_uri in labeled:
        cands = list(resolve(query))
        uris = [c.uri for c in cands]  # type: ignore[attr-defined]
        n += 1
        if expected_uri in uris:
            rank = uris.index(expected_uri) + 1
            rr += 1.0 / rank
            h1 += rank <= 1
            h3 += rank <= 3
            h5 += rank <= 5
            correct_scores.append(float(cands[rank - 1].score))  # type: ignore[attr-defined]
        else:
            misses.append(query)
    mean_score = sum(correct_scores) / len(correct_scores) if correct_scores else 0.0
    return RecallMetrics(
        n=n,
        recall_at_1=h1 / n if n else 0.0,
        recall_at_3=h3 / n if n else 0.0,
        recall_at_5=h5 / n if n else 0.0,
        mrr=rr / n if n else 0.0,
        mean_correct_score=mean_score,
        misses=tuple(misses),
    )
