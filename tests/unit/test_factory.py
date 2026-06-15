"""Composition-root selection (§2): live transport iff EOL_JWT is configured."""

from eol_genai_service.config import Settings
from eol_genai_service.factory import build_deps
from eol_genai_service.upstream.http_transport import HttpEolTransport


def test_build_deps_offline_without_jwt():
    deps = build_deps(Settings(eol_jwt=None))
    # Offline branch wires the fixture transport (a plain function), not the live HTTP transport.
    assert not isinstance(deps.client._transport, HttpEolTransport)


def test_build_deps_live_with_jwt():
    deps = build_deps(Settings(eol_jwt="token"))
    # Live branch wires the httpx transport (constructed, no network until a query runs).
    assert isinstance(deps.client._transport, HttpEolTransport)
