"""Phase 9 tests — hybrid analysis (report section 6.2)."""

from services.hybrid_analysis import analyze_hybrid


def test_hybrid_returns_expected_metrics(nasa_data):
    r = analyze_hybrid(nasa_data, latitude=33.5, longitude=-7.6)
    assert "error" not in r
    assert r["annual_energy_corrected_kwh"] > 0
    assert 0.0 <= r["complementarity_score"] <= 100.0
    assert -1.0 <= r["profile_correlation"] <= 1.0


def test_hybrid_shares_sum_to_100(nasa_data):
    r = analyze_hybrid(nasa_data, latitude=33.5, longitude=-7.6)
    assert abs(r["solar_share_pct"] + r["wind_share_pct"] - 100.0) < 0.5
    assert 0.0 <= r["solar_share_pct"] <= 100.0


def test_hybrid_p90_lower_than_p50(nasa_data):
    r = analyze_hybrid(nasa_data, latitude=33.5, longitude=-7.6)
    assert r["p90_annual_kwh"] <= r["p50_annual_kwh"]


def test_hybrid_p10_in_power_range(nasa_data):
    r = analyze_hybrid(nasa_data, latitude=33.5, longitude=-7.6)
    assert r["p10_power_kw"] >= 0.0
    assert 0.0 <= r["productive_hours_pct"] <= 100.0


def test_hybrid_produces_more_than_solar_alone(nasa_data):
    from services.solar_analysis import solar_hourly_series
    pv = solar_hourly_series(nasa_data, 33.5, -7.6)
    r = analyze_hybrid(nasa_data, latitude=33.5, longitude=-7.6)
    assert r["annual_energy_kwh"] >= float(pv.sum())
