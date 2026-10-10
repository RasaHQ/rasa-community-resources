"""Phase 9 tests — hourly wind chain (report sections 5-6)."""

import numpy as np

from services.wind_analysis import (
    analyze_wind, _weibull_mle, _power_curve, _wind_direction_name,
)


def test_wind_returns_expected_metrics(nasa_data):
    r = analyze_wind(nasa_data, hub_height_m=100.0, turbine_rating_kw=2000.0)
    assert "error" not in r
    assert 0.0 < r["ws_hub_avg"] < 30.0
    assert 0.0 < r["wind_power_density_corrected"]
    assert 0.0 < r["capacity_factor"] <= 1.0
    assert 0.0 < r["annual_energy_kwh"]
    assert r["hub_height_m"] == 100.0


def test_wind_hub_extrapolation_formula(nasa_data):
    """v_hub = v_50m * (z_hub / z_ref)^alpha."""
    r = analyze_wind(nasa_data, hub_height_m=100.0, reference_height_m=50.0,
                     wind_shear_exponent=1.0 / 7.0)
    ratio = r["ws_hub_avg"] / r["ws_50m_avg"]
    expected = 2.0 ** (1.0 / 7.0)
    assert abs(ratio - expected) < 0.05


def test_wind_exceedance_ordering(nasa_data):
    r = analyze_wind(nasa_data)
    assert r["p90_annual_kwh"] <= r["p75_annual_kwh"] <= r["p50_annual_kwh"]
    assert abs(r["p50_annual_kwh"] - r["annual_energy_corrected_kwh"]) < 1.0


def test_wind_power_density_formula(nasa_data):
    """WPD = 0.5 * rho * E[v^3]."""
    r = analyze_wind(nasa_data, wind_shear_exponent=1.0 / 7.0)
    rho = r["air_density"]
    v = r["ws_hub_avg"]
    approx = 0.5 * rho * v ** 3
    assert 0.1 < r["wind_power_density_corrected"] / approx < 4.0


def test_weibull_mle_matches_data():
    rng = np.random.default_rng(42)
    v = rng.weibull(2.0, size=200) * 7.0 + 0.5
    k, c = _weibull_mle(v)
    assert 1.5 < k < 2.5
    assert 4.0 < c < 9.0


def test_power_curve_cutoffs():
    v = np.array([0.0, 3.0, 12.0, 20.0, 25.0, 30.0])
    p = _power_curve(v, p_rated_kw=2000.0, v_cut_in=3.0, v_rated=12.0, v_cut_out=25.0)
    assert p[0] == 0.0
    assert 0.0 < p[1] < 2000.0
    assert abs(p[2] - 2000.0) < 1.0
    assert abs(p[4] - 2000.0) < 1.0  # at exactly v_cut_out -> still rated
    assert p[5] == 0.0  # above v_cut_out -> shutdown


def test_wind_direction_names():
    assert _wind_direction_name(0.0) == "N"
    assert _wind_direction_name(270.0) == "W"
    assert _wind_direction_name(45.0) == "NE"
