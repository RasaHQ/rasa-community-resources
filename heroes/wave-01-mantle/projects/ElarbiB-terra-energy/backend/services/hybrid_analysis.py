"""Hybrid solar + wind hourly analysis per TerraEnergy report (section 6.2).

Hourly AC profiles of PV and wind are summed. Complementarity is scored from
the correlation of the normalised profiles. No battery / grid / dispatch yet.
"""

import numpy as np
import pandas as pd

from services.solar_analysis import solar_hourly_series
from services.wind_analysis import wind_hourly_series

DAYS_PER_YEAR = 365.25


def analyze_hybrid(
    data: dict,
    latitude: float,
    longitude: float,
    solar_config: dict | None = None,
    wind_config: dict | None = None,
) -> dict:
    solar_config = solar_config or {}
    wind_config = wind_config or {}

    pv = solar_hourly_series(
        data, latitude, longitude,
        capacity_kw=solar_config.get("capacity_kw", 1000.0),
        tilt_deg=solar_config.get("tilt_deg"),
        azimuth_deg=solar_config.get("azimuth_deg"),
        inverter_efficiency=solar_config.get("inverter_efficiency", 0.96),
        dc_ac_ratio=solar_config.get("dc_ac_ratio", 1.2),
    )
    wind = wind_hourly_series(
        data,
        hub_height_m=wind_config.get("hub_height_m", 100.0),
        turbine_rating_kw=wind_config.get("turbine_rating_kw", 2000.0),
        v_cut_in=wind_config.get("v_cut_in", 3.0),
        v_rated=wind_config.get("v_rated", 12.0),
        v_cut_out=wind_config.get("v_cut_out", 25.0),
    )

    if pv.empty or wind.empty:
        return {"error": "No hourly data for hybrid analysis"}

    idx = pv.index.union(wind.index)
    pv = pv.reindex(idx).fillna(0.0)
    wind = wind.reindex(idx).fillna(0.0)
    combined = pv + wind

    days_covered = (idx.max() - idx.min()).days + 1

    # Complementarity: correlation of normalised hourly profiles
    pv_n = pv / pv.max() if pv.max() > 0 else pv
    wind_n = wind / wind.max() if wind.max() > 0 else wind
    if pv_n.std() > 0 and wind_n.std() > 0:
        corr = float(pv_n.corr(wind_n))
    else:
        corr = 0.0
    complementarity = min(100.0, max(0.0, (1 - corr) * 50.0))

    sum_pv = float(pv.sum())
    sum_wind = float(wind.sum())
    sum_combined = float(combined.sum())
    e_ann = sum_combined * (DAYS_PER_YEAR / days_covered)
    solar_share = sum_pv / sum_combined if sum_combined > 0 else 0.0
    wind_share = sum_wind / sum_combined if sum_combined > 0 else 0.0

    # Daily aggregates for P90
    daily = combined.resample('D').sum()
    daily = daily[daily > 0]
    cv = float(daily.std() / daily.mean()) if len(daily) > 1 and daily.mean() > 0 else 0.0
    p50 = e_ann
    p90 = p50 * (1 - 1.282 * cv)

    # P10 power: value exceeded 90% of the time
    p10_kw = float(np.percentile(combined.values, 10))

    # Productive hours
    productive = int((combined > combined.max() * 0.05).sum()) if combined.max() > 0 else 0
    productive_pct = productive / len(combined) * 100.0

    return {
        "annual_energy_kwh": round(sum_combined, 1),
        "annual_energy_corrected_kwh": round(e_ann, 1),
        "p50_annual_kwh": round(p50, 1),
        "p90_annual_kwh": round(p90, 1),
        "p10_power_kw": round(p10_kw, 1),
        "productive_hours_pct": round(productive_pct, 1),
        "solar_share_pct": round(solar_share * 100, 1),
        "wind_share_pct": round(wind_share * 100, 1),
        "complementarity_score": round(complementarity, 1),
        "profile_correlation": round(corr, 3),
        "days_covered": days_covered,
    }
