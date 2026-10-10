"""Phase 9 tests — equipment catalog and sizing (report section 4.2)."""

import asyncio

import pytest

from services.equipment_catalog import (
    INSTALLATION_TYPES, propose_system, get_modules, get_inverters,
)


def test_installation_types_occupation_factors():
    assert INSTALLATION_TYPES["roof"]["occupation_factor"] == 0.72
    assert INSTALLATION_TYPES["ground"]["occupation_factor"] == 0.45
    assert set(INSTALLATION_TYPES) == {"roof", "carport", "ground", "agrivoltaic", "floating"}


def test_propose_system_ground():
    r = propose_system(10000.0, support="ground")
    assert "error" not in r
    assert r["installation_type"] == "ground"
    assert r["usable_area_m2"] == pytest.approx(4500.0)
    m = r["module"]
    assert r["n_modules"] * m["area_m2"] <= r["usable_area_m2"] + 1.0
    assert r["proposed_kw"] == pytest.approx(r["n_modules"] * m["power_w"] / 1000.0)
    assert r["n_inverters"] >= 1
    assert r["inverter"] is not None


def test_propose_system_roof_and_defaults():
    r = propose_system(500.0)
    assert r["installation_type"] == "roof"
    assert r["usable_area_m2"] == pytest.approx(360.0)
    assert r["proposed_kw"] > 0


def test_propose_system_invalid_support_falls_back():
    r = propose_system(1000.0, support="moon")
    assert r["installation_type"] == "roof"


def test_propose_system_small_area():
    r = propose_system(2.0, support="roof")
    assert r["n_modules"] >= 0
    assert r["proposed_kw"] == 0.0 or r["proposed_kw"] > 0


def test_catalog_returns_entries():
    modules = get_modules(limit=5)
    inverters = get_inverters(limit=5)
    assert len(modules) == 5
    assert len(inverters) == 5
    for m in modules:
        assert m["power_w"] > 0 and m["area_m2"] > 0
    for i in inverters:
        assert i["pac_w"] > 0


def test_full_site_analysis_generates_system_proposal(nasa_data, monkeypatch):
    """site_context with a usable area must produce a system_proposal and
    derive the solar capacity from it (regression: `lang=` was passed to
    propose_system, which swallowed the TypeError and dropped the proposal)."""
    from services.site_scorer import full_site_analysis

    async def _fake_fetch(*a, **k):
        return nasa_data

    monkeypatch.setattr("services.nasa_client.fetch_power_data", _fake_fetch)

    site = asyncio.run(full_site_analysis(
        33.5, -7.6,
        "20230101", "20230131",
        solar_config={}, wind_config={},
        site_context={
            "installation_type": "roof",
            "available_area_m2": 600.0,
            "usable_area_m2": 540.0,
        },
        lang="fr",
    ))

    sp = site["system_proposal"]
    assert sp and sp.get("proposed_kw", 0) > 0
    assert site["solar_data"]["capacity_kw"] == sp["proposed_kw"]


def test_full_site_analysis_without_area_has_no_proposal(nasa_data, monkeypatch):
    from services.site_scorer import full_site_analysis

    async def _fake_fetch(*a, **k):
        return nasa_data

    monkeypatch.setattr("services.nasa_client.fetch_power_data", _fake_fetch)

    site = asyncio.run(full_site_analysis(
        33.5, -7.6,
        "20230101", "20230131",
        solar_config={}, wind_config={},
        site_context={},
        lang="fr",
    ))

    assert "system_proposal" not in site
    assert site["solar_data"]["capacity_kw"] == 1000.0
