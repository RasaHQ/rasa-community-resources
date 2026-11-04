"""Hourly wind energy chain per TerraEnergy technical report (section 6.1).

Chain: NASA POWER hourly wind at reference heights -> power-law hub height
extrapolation -> air density -> WPD = 0.5*rho*E[v^3] -> generic power curve
with cut-in/rated/cut-out -> losses -> CF / annual energy / P50/P75/P90.
"""

import math
import numpy as np
import pandas as pd
from scipy.optimize import brentq

from services.nasa_frame import (
    DAYS_PER_YEAR, HOURS_PER_YEAR, nasa_to_dataframe, reindex_hourly, interp_score,
)

_to_dataframe = nasa_to_dataframe
_reindex_hourly = reindex_hourly
_interp_score = interp_score

R_AIR = 287.058  # J/(kg*K) dry air


def _wind_direction_name(deg: float) -> str:
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(deg / 22.5) % 16
    return directions[idx]


def _weibull_mle(wind_speeds: np.ndarray) -> tuple[float, float]:
    """Maximum Likelihood Estimation for Weibull k (shape) and c (scale)."""
    v = wind_speeds[wind_speeds > 0]
    if len(v) < 10:
        return 0.0, 0.0

    n = len(v)
    ln_v = np.log(v)

    def objective(k):
        if k <= 0.01:
            return 1e10
        vk_k = v ** k
        return (np.sum(vk_k * ln_v) / np.sum(vk_k)) - (1.0 / k) - (np.sum(ln_v) / n)

    try:
        k = brentq(objective, 0.5, 5.0)
    except (ValueError, RuntimeError):
        k = 2.0

    c = (np.mean(v ** k)) ** (1.0 / k)
    return round(k, 3), round(c, 2)


def _weibull_pdf(v: float, k: float, c: float) -> float:
    if k <= 0 or c <= 0 or v < 0:
        return 0.0
    return (k / c) * (v / c) ** (k - 1) * np.exp(-(v / c) ** k)


def _iec_wind_class(ws_avg: float) -> str:
    if ws_avg >= 10.0:
        return "Class I (High Wind)"
    elif ws_avg >= 8.5:
        return "Class II (Medium Wind)"
    elif ws_avg >= 7.5:
        return "Class III (Low Wind)"
    else:
        return "Below Class III"


def _iec_turbulence_cat(ti: float) -> str:
    if ti >= 0.16:
        return "Category A (High Turbulence)"
    elif ti >= 0.14:
        return "Category B (Medium Turbulence)"
    else:
        return "Category C (Low Turbulence)"


def _nrel_pd_class(wpd_50m: float) -> int:
    thresholds = [200, 300, 400, 500, 600, 800]
    for i, t in enumerate(thresholds, 1):
        if wpd_50m < t:
            return i
    return 7


def _interp_score(x: float, x_lo: float, x_hi: float) -> float:
    if x <= x_lo:
        return 0.0
    if x >= x_hi:
        return 100.0
    return (x - x_lo) / (x_hi - x_lo) * 100.0


def _power_curve(v: np.ndarray, p_rated_kw: float, v_cut_in: float,
                 v_rated: float, v_cut_out: float) -> np.ndarray:
    """Generic cubic power curve."""
    p = np.zeros_like(v, dtype=float)
    ramp = (v >= v_cut_in) & (v < v_rated)
    p[ramp] = p_rated_kw * (v[ramp] ** 3) / (v_rated ** 3)
    p[(v >= v_rated) & (v <= v_cut_out)] = p_rated_kw
    return p


def _wind_hourly(
    data: dict,
    hub_height_m: float = 100.0,
    turbine_rating_kw: float = 2000.0,
    v_cut_in: float = 3.0,
    v_rated: float = 12.0,
    v_cut_out: float = 25.0,
    wake_loss: float = 0.05,
    electrical_loss: float = 0.03,
    other_loss: float = 0.02,
    availability: float = 0.97,
    reference_height_m: float = 50.0,
    wind_shear_exponent: float | None = None,
) -> dict:
    df = _to_dataframe(data)
    if df.empty:
        return {"error": "No data available"}

    s = _reindex_hourly(df)

    ws_ref = s['WS50M'] if 'WS50M' in s.columns else pd.Series(0.0, index=s.index)
    ws_10m = s['WS10M'] if 'WS10M' in s.columns else pd.Series(np.nan, index=s.index)
    wd_ref = s['WD50M'] if 'WD50M' in s.columns else pd.Series(0.0, index=s.index)
    rho_data = s['RHOA'] if 'RHOA' in s.columns else pd.Series(np.nan, index=s.index)
    ps_data = s['PS'] if 'PS' in s.columns else pd.Series(np.nan, index=s.index)
    t2m = s['T2M'] if 'T2M' in s.columns else pd.Series(np.nan, index=s.index)

    # Shear exponent
    if wind_shear_exponent is None:
        ws10_ok = ws_10m.dropna()
        if len(ws10_ok) > 0 and float(ws10_ok.mean()) > 0 and float(ws_ref.mean()) > 0:
            alpha = math.log(float(ws_ref.mean()) / float(ws10_ok.mean())) / math.log(50.0 / 10.0)
        else:
            alpha = 1.0 / 7.0
    else:
        alpha = wind_shear_exponent

    # Hub height extrapolation: v(z) = v(zref) * (z / zref)^alpha
    v_hub = ws_ref * ((hub_height_m / reference_height_m) ** alpha)

    # Air density
    rho = rho_data.copy()
    mask = rho.isna()
    if mask.any():
        p_pa = ps_data * 1000.0
        t_k = t2m + 273.15
        rho_fill = p_pa / (R_AIR * t_k)
        rho = rho.where(~mask, rho_fill)
    rho = rho.fillna(1.225)
    rho_mean = float(rho.mean())

    # WPD = 0.5 * rho * E[v^3]
    wpd = 0.5 * float((rho * v_hub ** 3).mean())

    # Power curve + losses
    p_kw = _power_curve(v_hub.values, turbine_rating_kw, v_cut_in, v_rated, v_cut_out)
    f_sys = ((1 - wake_loss) * (1 - electrical_loss) * (1 - other_loss) * availability)
    p_kw = p_kw * f_sys
    p_kw = pd.Series(p_kw, index=s.index)

    days_covered = (s.index.max() - s.index.min()).days + 1
    sum_kwh = float(p_kw.sum())
    e_ann = sum_kwh * (DAYS_PER_YEAR / days_covered)

    capacity_factor = e_ann / (turbine_rating_kw * HOURS_PER_YEAR)
    specific_yield = e_ann / turbine_rating_kw

    daily_ac = p_kw.resample('D').sum()
    daily_ac = daily_ac[daily_ac > 0]
    ac_cv = float(daily_ac.std() / daily_ac.mean()) if len(daily_ac) > 1 and daily_ac.mean() > 0 else 0.0
    p50 = e_ann
    p75 = p50 * (1 - 0.674 * ac_cv)
    p90 = p50 * (1 - 1.282 * ac_cv)

    # Eligible hours
    eligible = ((v_hub >= v_cut_in) & (v_hub <= v_cut_out)).sum()
    total_valid = int(v_hub.notna().sum()) or 1
    eligible_pct = eligible / total_valid * 100.0

    # Dominant direction
    wd_clean = wd_ref.dropna()
    if len(wd_clean) > 0:
        dir_rad = np.radians(wd_clean)
        avg_sin = np.sin(dir_rad).mean()
        avg_cos = np.cos(dir_rad).mean()
        dominant_deg = math.degrees(math.atan2(avg_sin, avg_cos)) % 360
        dominant_direction = _wind_direction_name(dominant_deg)
    else:
        dominant_direction = "N/A"

    # Turbulence intensity
    v_hub_clean = v_hub.dropna()
    turbulence_intensity = float(v_hub_clean.std() / v_hub_clean.mean()) if len(v_hub_clean) > 0 and v_hub_clean.mean() > 0 else 0.0

    ws_hub_mean = float(v_hub.mean())

    return {
        "hub_speed_hourly": v_hub.values,
        "power_hourly": p_kw.values,
        "times": s.index,
        "ws_hub_mean": ws_hub_mean,
        "ws_2m_mean": float(s['WS2M'].mean()) if 'WS2M' in s.columns else 0.0,
        "ws_10m_mean": float(ws_10m.mean()) if not ws_10m.isna().all() else 0.0,
        "air_density": rho_mean,
        "wpd": wpd,
        "sum_kwh": sum_kwh,
        "e_ann": e_ann,
        "specific_yield": specific_yield,
        "capacity_factor": capacity_factor,
        "p50": p50,
        "p75": p75,
        "p90": p90,
        "ac_cv": ac_cv,
        "eligible_pct": eligible_pct,
        "dominant_direction": dominant_direction,
        "turbulence_intensity": turbulence_intensity,
        "weibull_k": None,
        "weibull_c": None,
        "shear_alpha": alpha,
        "days_covered": days_covered,
    }


def analyze_wind(
    data: dict,
    hub_height_m: float = 100.0,
    turbine_rating_kw: float = 2000.0,
    v_cut_in: float = 3.0,
    v_rated: float = 12.0,
    v_cut_out: float = 25.0,
    wake_loss: float = 0.05,
    electrical_loss: float = 0.03,
    other_loss: float = 0.02,
    availability: float = 0.97,
    reference_height_m: float = 50.0,
    wind_shear_exponent: float | None = None,
) -> dict:
    r = _wind_hourly(
        data,
        hub_height_m=hub_height_m,
        turbine_rating_kw=turbine_rating_kw,
        v_cut_in=v_cut_in,
        v_rated=v_rated,
        v_cut_out=v_cut_out,
        wake_loss=wake_loss,
        electrical_loss=electrical_loss,
        other_loss=other_loss,
        availability=availability,
        reference_height_m=reference_height_m,
        wind_shear_exponent=wind_shear_exponent,
    )
    if r.get("error"):
        return r

    df = _to_dataframe(data)
    s = _reindex_hourly(df)

    v_hub = pd.Series(r["hub_speed_hourly"], index=r["times"])
    wd_ref = s['WD50M'] if 'WD50M' in s.columns else pd.Series(0.0, index=s.index)

    weibull_k, weibull_c = _weibull_mle(v_hub.values)

    # Histogram
    hist_bins = np.arange(0, 22, 1)
    hist, edges = np.histogram(v_hub.dropna().values, bins=hist_bins)
    total = hist.sum()
    histogram = {
        "bins": [f"{int(edges[i])}-{int(edges[i+1])}" for i in range(len(hist))],
        "frequencies": [round(int(h) / total * 100, 1) for h in hist] if total > 0 else [0] * len(hist),
        "weibull_pdf": [round(_weibull_pdf(float(edges[i] + 0.5), weibull_k, weibull_c) * 100, 2)
                        for i in range(len(hist))] if weibull_k > 0 else [],
    }

    # Wind rose
    wind_rose = {}
    if len(wd_ref.dropna()) > 0:
        for name in ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]:
            wind_rose[name] = 0
        for deg in wd_ref.dropna():
            name = _wind_direction_name(deg)
            wind_rose[name] = wind_rose.get(name, 0) + 1
        tot = sum(wind_rose.values()) or 1
        wind_rose = {k: round(v / tot * 100, 1) for k, v in wind_rose.items()}

    wind_power_density_reference = 0.5 * 1.225 * (float(s['WS50M'].mean()) ** 3)
    wind_power_density_corrected = r["wpd"]

    # Score: speed + WPD + eligible + stability
    speed_score = _interp_score(r["ws_hub_mean"], 3.0, 9.0)
    wpd_score = _interp_score(wind_power_density_corrected, 100.0, 500.0)
    elig_score = _interp_score(r["eligible_pct"], 30.0, 85.0)
    stab_score = 100.0 - _interp_score(r["ac_cv"], 0.2, 1.0)
    score = 0.30 * speed_score + 0.30 * wpd_score + 0.20 * elig_score + 0.20 * stab_score

    return {
        "ws_2m_avg": round(r["ws_2m_mean"], 2),
        "ws_50m_avg": round(float(s['WS50M'].mean()) if 'WS50M' in s.columns else 0.0, 2),
        "ws_hub_avg": round(r["ws_hub_mean"], 2),
        "hub_height_m": hub_height_m,
        "turbine_rating_kw": turbine_rating_kw,
        "wind_power_density": round(wind_power_density_reference, 1),
        "wind_power_density_corrected": round(wind_power_density_corrected, 1),
        "dominant_direction": r["dominant_direction"],
        "eligible_hours_pct": round(r["eligible_pct"], 1),
        "capacity_factor": round(r["capacity_factor"], 4),
        "specific_yield_kwh_kw": round(r["specific_yield"], 1),
        "annual_energy_kwh": round(r["sum_kwh"], 1),
        "annual_energy_corrected_kwh": round(r["e_ann"], 1),
        "p50_annual_kwh": round(r["p50"], 1),
        "p75_annual_kwh": round(r["p75"], 1),
        "p90_annual_kwh": round(r["p90"], 1),
        "score": round(min(100.0, max(0.0, score)), 1),
        "wind_rose": wind_rose,
        "monthly_ws": {str(m): round(float(v_hub[v_hub.index.month == m].mean()), 2) if len(v_hub[v_hub.index.month == m]) > 0 else 0.0 for m in range(1, 13)},
        "variability": round(r["ac_cv"], 3),
        "weibull_k": weibull_k,
        "weibull_c": weibull_c,
        "turbulence_intensity": round(r["turbulence_intensity"], 3),
        "iec_wind_class": _iec_wind_class(r["ws_hub_mean"]),
        "iec_turbulence_cat": _iec_turbulence_cat(r["turbulence_intensity"]),
        "nrel_pd_class": _nrel_pd_class(wind_power_density_corrected),
        "wind_shear_exponent": round(r["shear_alpha"], 3),
        "air_density": round(r["air_density"], 4),
        "wind_speed_histogram": histogram,
        "days_covered": r["days_covered"],
    }


def wind_hourly_series(
    data: dict,
    hub_height_m: float = 100.0,
    turbine_rating_kw: float = 2000.0,
    v_cut_in: float = 3.0,
    v_rated: float = 12.0,
    v_cut_out: float = 25.0,
) -> pd.Series:
    r = _wind_hourly(
        data,
        hub_height_m=hub_height_m,
        turbine_rating_kw=turbine_rating_kw,
        v_cut_in=v_cut_in,
        v_rated=v_rated,
        v_cut_out=v_cut_out,
    )
    if r.get("error"):
        return pd.Series(dtype=float)
    return pd.Series(r["power_hourly"], index=r["times"])
