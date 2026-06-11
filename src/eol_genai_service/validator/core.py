"""The single validator (T009) — no bypass (Constitution Principle II).

One entry point, :func:`validate`, asserts three things about every query before it may reach
EOL:

1. ``MISSING_LIMIT``   — an explicit ``LIMIT <n>`` clause is present.
2. ``UNRESOLVED_URI``  — every ontology-URI literal in the query is a member of the resolved
   set (no model-invented URIs). Comparison is **case-sensitive**.
3. ``NOT_READ_ONLY``   — the query contains no write clause.

Backs SC-002 (zero invented URIs) and SC-003 (zero mutations). See
contracts/validator.md. Server-side mutation rejection by EOL is defense-in-depth, not a
substitute for assertion 3.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

ViolationCode = str  # one of: MISSING_LIMIT, UNRESOLVED_URI, NOT_READ_ONLY

# An explicit numeric LIMIT clause. Cypher keywords are case-insensitive.
_LIMIT_RE = re.compile(r"\blimit\b\s+\d+", re.IGNORECASE)

# Ontology URIs look like VT_0001259, PATO_0000117, RO_0002471 — UPPERCASE prefix + digits.
_URI_RE = re.compile(r"\b[A-Z][A-Z0-9]*_[0-9]+\b")

# Write clauses that make a query non-read-only. Whole-word, case-insensitive.
_WRITE_KEYWORDS = ("CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "FOREACH")
_WRITE_RE = re.compile(r"\b(?:" + "|".join(_WRITE_KEYWORDS) + r")\b", re.IGNORECASE)

# Quoted string literals (single or double quoted). Contents are blanked before scanning for
# write keywords / LIMIT so a string value like {name: 'CREATE'} is not a false positive.
_STRING_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


@dataclass(frozen=True)
class Violation:
    """A single failed assertion."""

    code: ViolationCode
    detail: str = ""


@dataclass(frozen=True)
class Verdict:
    """The validator's decision. ``ok`` is True only when there are no violations."""

    ok: bool
    violations: tuple[Violation, ...] = field(default_factory=tuple)


def _strip_strings(query: str) -> str:
    """Replace the contents of quoted string literals with empty quotes."""
    return _STRING_RE.sub("''", query)


def validate(query: str, resolved_uris: Iterable[str]) -> Verdict:
    """Validate ``query`` against the resolved-URI allow-list.

    ``resolved_uris`` is the exact set of URIs produced by resolution for this request. Any
    URI-shaped literal in the query that is not in this set is a violation (case-sensitive).
    """
    resolved = set(resolved_uris)
    violations: list[Violation] = []

    # For LIMIT and read-only checks, ignore the contents of string literals.
    scannable = _strip_strings(query)

    # 1. LIMIT present
    if not _LIMIT_RE.search(scannable):
        violations.append(Violation("MISSING_LIMIT", "no explicit LIMIT <n> clause"))

    # 2. All ontology URIs resolved (scan the ORIGINAL query — URIs often live in string values)
    for uri in _URI_RE.findall(query):
        if uri not in resolved:
            violations.append(
                Violation("UNRESOLVED_URI", f"URI {uri!r} not produced by resolution")
            )

    # 3. Read-only
    for match in _WRITE_RE.finditer(scannable):
        violations.append(Violation("NOT_READ_ONLY", f"write clause {match.group(0).upper()!r}"))

    return Verdict(ok=not violations, violations=tuple(violations))
