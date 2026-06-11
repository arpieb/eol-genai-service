"""Embedded term catalog index — cache + rebuild (T048; T011 embeddings deferred).

Protects the small, 2018-era upstream (Constitution Principle VII): term lists are enumerated
once and cached with an explicit TTL and invalidation, so query-time resolution hits the cache,
not EOL. The catalog is rebuildable from a source enumerator (offline: the fixture catalog; live:
the self-describing graph). The embedding/vector-index half is tracked separately (T011/research
R1-R2); this module is the cache + rebuild surface those build on.

The clock is injected so TTL behavior is deterministic and testable.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Generic, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    """A minimal time-to-live cache with explicit invalidation (Principle VII)."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._store: dict[str, tuple[float, V]] = {}

    def get(self, key: str) -> V | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: V) -> None:
        self._store[key] = (self._clock() + self._ttl, value)

    def invalidate(self, key: str | None = None) -> None:
        """Drop one key, or the whole cache when ``key`` is None."""
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)


class CatalogIndex(Generic[V]):
    """A versioned, cached view of the enumerated term catalog, rebuildable on demand."""

    _CACHE_KEY = "terms"

    def __init__(
        self,
        enumerate_terms: Callable[[], list[V]],
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._enumerate = enumerate_terms
        self._cache: TTLCache[list[V]] = TTLCache(ttl_seconds, clock)
        self._version = 0

    @property
    def version(self) -> int:
        return self._version

    def terms(self) -> list[V]:
        """Return the cached term list, enumerating (and caching) on a miss."""
        cached = self._cache.get(self._CACHE_KEY)
        if cached is not None:
            return cached
        return self._populate()

    def rebuild(self) -> list[V]:
        """Force a fresh enumeration, bump the version, and refresh the cache."""
        self._cache.invalidate()
        return self._populate()

    def _populate(self) -> list[V]:
        terms = self._enumerate()
        self._cache.set(self._CACHE_KEY, terms)
        self._version += 1
        return terms
