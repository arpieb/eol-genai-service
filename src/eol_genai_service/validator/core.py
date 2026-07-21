"""The single validator (T009) — no bypass (Constitution Principle II).

One entry point, :func:`validate`, asserts four things about every query before it may reach
EOL:

1. ``MISSING_LIMIT``   — an explicit ``LIMIT <n>`` clause is present (required by EOL).
2. ``UNRESOLVED_URI``  — every ontology-URI literal in the query is a member of the resolved
   set (no model-invented URIs). Comparison is **case-sensitive**.
3. ``NOT_READ_ONLY``   — the query contains no write clause.
4. ``UNSUPPORTED_ORDER_BY`` — the query contains no ``ORDER BY`` clause. EOL's Cypher gateway
   rejects ``ORDER BY`` with an opaque HTTP 403; we reject it here with an actionable message so
   the caller sorts client-side instead of guessing at the upstream failure.

Backs SC-002 (zero invented URIs) and SC-003 (zero mutations). See
contracts/validator.md. Server-side mutation rejection by EOL is defense-in-depth, not a
substitute for assertion 3.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

ViolationCode = str  # one of: MISSING_LIMIT, UNRESOLVED_URI, NOT_READ_ONLY, UNSUPPORTED_ORDER_BY

# An explicit numeric LIMIT clause. Cypher keywords are case-insensitive.
_LIMIT_RE = re.compile(r"\blimit\b\s+\d+", re.IGNORECASE)

# An ORDER BY clause. EOL's Cypher endpoint 403s on ORDER BY, so it is rejected here. Any run of
# whitespace may separate the keywords; matched on the string-stripped query so an 'order by'
# inside a quoted value is not a false positive.
_ORDER_BY_RE = re.compile(r"\border\s+by\b", re.IGNORECASE)

# Ontology URI literals. EOL stores FULL URIs (http://purl.obolibrary.org/obo/VT_0001259,
# http://eol.org/schema/terms/ExtinctionStatus); the offline fixtures use the short form
# (VT_0001259). Match either — the full-URL alternative is tried first and consumes the whole URL,
# so a short id embedded inside a full URI is not separately extracted. Comparison against the
# resolved set is whole-token and case-sensitive (preserves SC-002 "no invented URIs").
_URI_RE = re.compile(r"https?://[^\s'\"]+|\b[A-Z][A-Z0-9]*_[0-9]+\b")

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

    # 1b. No ORDER BY (EOL's Cypher gateway rejects it with an opaque HTTP 403)
    if _ORDER_BY_RE.search(scannable):
        violations.append(
            Violation(
                "UNSUPPORTED_ORDER_BY",
                "ORDER BY is rejected by EOL's Cypher endpoint (HTTP 403); "
                "remove it and sort the rows client-side",
            )
        )

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
