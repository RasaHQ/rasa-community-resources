"""Tests for the keyless tile proxy (services/tile_proxy.py, routers/map.py)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from main import app
from services import tile_proxy


@pytest.fixture(autouse=True)
def clear_cache():
    tile_proxy._CACHE.clear()
    yield
    tile_proxy._CACHE.clear()


def make_fetch(variant: str):
    """Canned fetch: real tiles for esri/opentopo, error tiles, then OSM fallback."""

    async def _fetch(url: str):
        if "opentopomap" in url:
            if variant == "relief-ok":
                return (200, "image/png", b"\x89PNG" + b"R" * 9000)
            # The exact OpenTopoMap error-tile payload (4343 bytes).
            return (200, "image/png", b"\x89PNG" + b"O" * 4339)
        if "arcgisonline" in url:
            if variant == "esri-ok":
                return (200, "image/jpeg", b"\xff\xd8" + b"J" * 9000)
            # The exact Esri error-tile payload (2521 bytes).
            return (200, "image/jpeg", b"\xff\xd8" + b"E" * 2519)
        if "openstreetmap" in url:
            if variant == "osm-broken":
                return (500, "text/html", b"server error")
            return (200, "image/png", b"\x89PNG" + b"M" * 6000)
        return (500, "text/html", b"unhandled")

    return _fetch


def test_error_image_detected_and_swapped(monkeypatch):
    """An HTTP-200 Esri error image must be replaced by the OSM fallback."""
    monkeypatch.setattr(tile_proxy, "_fetch", make_fetch("esri-err"))
    body, ctype, source = asyncio.run(tile_proxy.get_tile("satellite", 7, 42, 24))
    assert source == "carte"
    assert ctype == "image/png"
    assert body.startswith(b"\x89PNG")


def test_valid_tile_passthrough(monkeypatch):
    """A genuine Esri image travels through untouched."""
    monkeypatch.setattr(tile_proxy, "_fetch", make_fetch("esri-ok"))
    body, ctype, source = asyncio.run(tile_proxy.get_tile("satellite", 7, 42, 24))
    assert source == "satellite"
    assert ctype == "image/jpeg"
    assert len(body) > 2500


def test_relief_error_detection(monkeypatch):
    monkeypatch.setattr(tile_proxy, "_fetch", make_fetch("relief-err"))
    body, ctype, source = asyncio.run(tile_proxy.get_tile("relief", 7, 42, 24))
    assert source == "carte"


def test_all_providers_down_raises(monkeypatch):
    monkeypatch.setattr(tile_proxy, "_fetch", make_fetch("osm-broken"))
    with pytest.raises(RuntimeError):
        asyncio.run(tile_proxy.get_tile("terrain", 7, 42, 24))


def test_unknown_provider_raises_keyerror():
    with pytest.raises(KeyError):
        asyncio.run(tile_proxy.get_tile("carto", 7, 42, 24))


def test_caching_no_second_fetch(monkeypatch):
    calls = []

    async def counting_fetch(url: str):
        calls.append(url)
        return await make_fetch("esri-ok")(url)

    monkeypatch.setattr(tile_proxy, "_fetch", counting_fetch)
    asyncio.run(tile_proxy.get_tile("satellite", 7, 42, 24))
    asyncio.run(tile_proxy.get_tile("satellite", 7, 42, 24))
    assert len(calls) == 1


def test_endpoint_unknown_provider_400():
    client = TestClient(app)
    r = client.get("/api/map/tile", params={"provider": "carto", "z": 3, "x": 3, "y": 3})
    assert r.status_code == 400


def test_providers_listed():
    client = TestClient(app)
    r = client.get("/api/map/providers")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"satellite", "terrain", "relief", "carte"}