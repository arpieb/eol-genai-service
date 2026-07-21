"""EOL Cypher client skeleton (T008 — Constitution Principle VII).

Owns the upstream boundary: attaches the shared admin JWT, requests ``format=cypher``, applies a
deliberate result cap (flagging truncation, SC-005), and maps transport failures to an explicit
unavailable signal (FR-013) — distinct from an empty result, which is a valid answer (FR-010).
Bounded retries with backoff, never a tight loop.

The network is injected as a :data:`Transport` callable so this logic is testable offline and
there is exactly one place that talks to EOL. Empty rows are returned as a valid result, not an
error.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from eol_genai_service.config import Settings

# The transport boundary: (query, fmt) -> rows. Raises on timeout/transport/HTTP error.
Transport = Callable[[str, str], list[dict[str, object]]]


class UpstreamUnavailable(Exception):
    """EOL was unavailable / timed out / returned an error (FR-013).

    Distinct from an empty result set (which is valid, FR-010) and from internal service errors.
    """


class UpstreamHttpError(Exception):
    """EOL returned a non-2xx HTTP response.

    Carries the status code and (truncated) response body so opaque upstream failures stay
    debuggable — e.g. the HTTP 403 EOL returns for a rejected ``ORDER BY``. The transport raises
    this instead of a bare ``httpx.HTTPStatusError`` (whose message omits the body); the client
    surfaces the text through :class:`UpstreamUnavailable`.
    """

    def __init__(self, status_code: int, reason: str, body: str = "") -> None:
        self.status_code = status_code
        self.reason = reason
        self.body = body
        message = f"EOL returned HTTP {status_code} {reason}".rstrip()
        detail = body.strip()
        if detail:
            message += f": {detail}"
        super().__init__(message)

    @property
    def is_client_error(self) -> bool:
        """4xx — a deterministic rejection (auth, forbidden, bad query). Retrying won't help."""
        return 400 <= self.status_code < 500


@dataclass(frozen=True)
class UpstreamResult:
    """Rows returned by EOL plus whether the deliberate cap truncated them (SC-005)."""

    rows: list[dict[str, object]]
    truncated: bool


class EolCypherClient:
    """Read-only client for ``https://eol.org/service/cypher``.

    ``transport`` is the only thing that touches the network; the default ``None`` is wired to an
    httpx-backed transport at the composition root (not constructed here, to keep this unit
    offline-testable).
    """

    def __init__(self, settings: Settings, transport: Transport) -> None:
        self._settings = settings
        self._transport = transport

    def fetch(self, query: str) -> UpstreamResult:
        """Execute ``query`` against EOL and return capped rows.

        Bounded retry with backoff on transport failure; the final failure raises
        :class:`UpstreamUnavailable`. Empty rows are returned normally (not an error, FR-010).
        """
        attempts = self._settings.upstream_max_retries + 1
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                rows = self._transport(query, self._settings.eol_format)
            except UpstreamHttpError as exc:
                # 4xx is deterministic (auth/forbidden/bad query) — a retry fails identically, so
                # fail fast rather than hammering EOL. The message carries the status + body so the
                # opaque failure (e.g. a 403) is debuggable.
                if exc.is_client_error:
                    raise UpstreamUnavailable(str(exc)) from exc
                last_exc = exc  # 5xx may be transient — fall through to bounded retry
                continue
            except Exception as exc:  # noqa: BLE001 - any transport failure is "unavailable"
                last_exc = exc
                continue  # bounded retry; backoff is applied by the transport layer
            return self._cap(rows)
        raise UpstreamUnavailable(str(last_exc) if last_exc else "upstream unavailable")

    def _cap(self, rows: list[dict[str, object]]) -> UpstreamResult:
        cap = self._settings.result_cap
        if len(rows) > cap:
            return UpstreamResult(rows=rows[:cap], truncated=True)
        return UpstreamResult(rows=rows, truncated=False)
