"""Labeled predicate-resolution set for the recall@k bake-off (research R2).

Each entry is ``(user phrase, expected EOL term name)``. The harness maps the expected name to its
URI from the live catalog (so URIs aren't hardcoded/staleness-prone). Names here are confirmed to
exist in EOL's predicate catalog; phrases are realistic paraphrases that point to one term.
"""

from __future__ import annotations

# (query phrase, expected predicate term name)
LABELED: list[tuple[str, str]] = [
    ("what is the body mass", "body mass"),
    ("how much does it weigh", "body mass"),
    ("what habitat does it live in", "habitat"),
    ("where does it live", "habitat"),
    ("how long is its body", "body length"),
    ("body length", "body length"),
    ("geographic distribution", "geographic distribution"),
    ("where is it found", "geographic distribution"),
    ("how does it move around", "locomotion"),
    ("mode of locomotion", "locomotion"),
    ("what is its conservation status", "conservation status"),
    ("is it endangered", "conservation status"),
    ("trophic level", "trophic level"),
    ("what is its body temperature", "body temperature"),
]
