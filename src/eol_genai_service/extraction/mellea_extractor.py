"""Mellea-constrained NL→intent extractor (T014 — Constitution Principle V).

The live service-side extractor: turns a natural-language question into a format-valid
:class:`QueryIntent` using Mellea's constrained decoding on a local Granite/Ollama model (the
default per research R3 / constitution v1.1.0). It implements the same :class:`Extractor` protocol
as the offline ``RuleBasedExtractor``, so it drops into the pipeline unchanged.

What constrained decoding buys (verified by spike against `granite4.1:3b`): the model output is
**always** schema-valid JSON that parses into the typed intent. What it does NOT buy: semantic
correctness — the extractor emits raw surface phrases, and grounding (term→URI) + the validator
downstream are what keep a wrong guess from becoming a wrong answer (Principle II/IV).

Spike findings (research R3 §spike):
- Canonical shapes (US-1..US-5) extract correctly at 3B.
- Genuinely compositional questions (US-7, e.g. "pollinators that visit plants humans use") may be
  flattened to a single shape rather than `novel`. This is safe: their unnamed/abstract refs fail
  to resolve confidently, so the pipeline returns needs_clarification / out_of_capability — never a
  fabricated answer. The frontier backend (`EOL_SERVICE_MODEL_BACKEND=anthropic`) is the configured
  upgrade for this tail.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from eol_genai_service.config import Settings
from eol_genai_service.extraction.intent import QueryIntent

# The constrained-decoding schema. Mellea's `format=` enforces this shape on the model output.
_SHAPES = Literal[
    "single_fact",
    "categorical_attribute",
    "association",
    "aggregate_count",
    "lineage",
    "n_hop_chain",
    "novel",
]


class _IntentSchema(BaseModel):
    shape: _SHAPES
    taxon_refs: list[str] = Field(default_factory=list)
    predicate_refs: list[str] = Field(default_factory=list)
    rollup: bool = False


# Prompt refined during the spike to gate aggregate_count on counting questions and route
# multi-relationship questions to novel.
_PROMPT = (
    "Extract a structured query intent from a biodiversity question. Choose shape:\n"
    "- single_fact: one attribute (size/mass/length/etc.) of ONE named organism.\n"
    "- categorical_attribute: a category (e.g. habitat) of one named organism.\n"
    "- association: one named organism eats/interacts-with another.\n"
    "- aggregate_count: ONLY counting questions ('how many', 'number of') with NO single organism"
    " named.\n"
    "- lineage: ancestry/classification of one named organism.\n"
    "- novel: compositional questions chaining multiple relationships, or anything not above.\n"
    "Rules: if a specific organism is named, NEVER use aggregate_count. If the question chains two"
    " relationships (X that do Y), use novel.\n"
    "taxon_refs = named organism(s), verbatim (omit answer-type words like 'pollinators'). "
    "predicate_refs = attribute/relationship phrase(s), verbatim. rollup=true only for"
    " aggregate_count over a general category.\n"
    'Question: "{question}"'
)


class MelleaExtractor:
    """Constrained-decoded extractor over a local (or configured) Mellea backend.

    The Mellea session connects to the backend (Ollama by default) on first use, so constructing
    this object is cheap and does not require the backend to be up until ``extract`` is called.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or Settings()
        self._backend = settings.service_model_backend
        self._model_id = settings.service_model_id
        self._session = None  # lazy — created on first extract()

    def _ensure_session(self):
        if self._session is None:
            import mellea  # imported lazily so the backend is only required at call time

            self._session = mellea.start_session(
                backend_name=self._backend, model_id=self._model_id
            )
        return self._session

    def extract(self, question: str) -> QueryIntent:
        session = self._ensure_session()
        result = session.instruct(_PROMPT.format(question=question), format=_IntentSchema)
        try:
            parsed = _IntentSchema.model_validate_json(result.value)
        except Exception:
            # Constrained decoding should guarantee a parse; if it ever fails, fall back to novel
            # rather than guessing (never fabricate).
            return QueryIntent(shape="novel")
        return QueryIntent(
            shape=parsed.shape,
            taxon_refs=tuple(parsed.taxon_refs),
            predicate_refs=tuple(parsed.predicate_refs),
            rollup=parsed.rollup,
        )
