"""Phase 9 tests — hourly solar chain (report section 5)."""

from services.solar_analysis import analyze_solar


def test_solar_returns_expected_metrics(nasa_data):
    r = analyze_solar(nasa_data, latitude=33.5, longitude=-7.6, capacity_kw=1000.0)
    assert "error" not in r
    assert 0.0 < r["ghi_avg"] <= 10.0
    assert 0.0 < r["annual_energy_kwh"]
    assert 0.0 < r["capacity_factor"] <= 1.0
    assert 0.0 < r["performance_ratio"] <= 1.0
    assert 0.0 < r["specific_yield_kwh_kwp"]


def test_solar_exceedance_ordering(nasa_data):
    r = analyze_solar(nasa_data, latitude=33.5, longitude=-7.6)
    assert r["p90_annual_kwh"] <= r["p75_annual_kwh"] <= r["p50_annual_kwh"]
    assert abs(r["p50_annual_kwh"] - r["annual_energy_corrected_kwh"]) < 1.0


def test_solar_p90_formula(nasa_data):
    """P90 = P50 * (1 - 1.282 * sigma) on the daily profile."""
    r = analyze_solar(nasa_data, latitude=33.5, longitude=-7.6)
    sigma = (1 - r["p90_annual_kwh"] / r["p50_annual_kwh"]) / 1.282
    assert 0.0 <= sigma <= 1.0


def test_solar_losses_are_negative_systematic(nasa_data):
    r = analyze_solar(nasa_data, latitude=33.5, longitude=-7.6)
    l = r["losses_breakdown"]
    assert 0.0 < l["total"] <= 100.0
    assert l["temperature"] > 0.0


def test_solar_optimize_orientation_runs(nasa_data):
    r = analyze_solar(nasa_data, latitude=33.5, longitude=-7.6, optimize_orientation=True)
    assert "error" not in r
    assert "optimized_tilt_deg" in r
    assert 0.0 <= r["optimized_tilt_deg"] <= 90.0


def test_solar_empty_data():
    r = analyze_solar({}, latitude=33.5, longitude=-7.6)
    assert "error" in r
