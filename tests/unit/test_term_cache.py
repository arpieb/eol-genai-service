"""Term-list TTL cache + catalog rebuild (T048 — Constitution Principle VII)."""

from eol_genai_service.resolution.index import CatalogIndex, TTLCache


class FakeClock:
    """A controllable monotonic clock for deterministic TTL tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_ttl_cache_hits_within_ttl_and_expires_after():
    clock = FakeClock()
    cache: TTLCache[str] = TTLCache(ttl_seconds=10, clock=clock)
    cache.set("k", "v")
    assert cache.get("k") == "v"  # within TTL
    clock.now = 10.0
    assert cache.get("k") is None  # expired


def test_ttl_cache_invalidation():
    cache: TTLCache[str] = TTLCache(ttl_seconds=10, clock=FakeClock())
    cache.set("a", "1")
    cache.set("b", "2")
    cache.invalidate("a")
    assert cache.get("a") is None
    assert cache.get("b") == "2"
    cache.invalidate()  # clear all
    assert cache.get("b") is None


def test_catalog_index_caches_then_rebuilds():
    calls = {"n": 0}

    def enumerate_terms():
        calls["n"] += 1
        return ["VT_0001259", "RO_0002470"]

    clock = FakeClock()
    index = CatalogIndex(enumerate_terms, ttl_seconds=100, clock=clock)

    assert index.terms() == ["VT_0001259", "RO_0002470"]
    assert index.terms() == ["VT_0001259", "RO_0002470"]
    assert calls["n"] == 1  # second call served from cache, not re-enumerated
    assert index.version == 1

    index.rebuild()
    assert calls["n"] == 2  # rebuild forces re-enumeration
    assert index.version == 2
