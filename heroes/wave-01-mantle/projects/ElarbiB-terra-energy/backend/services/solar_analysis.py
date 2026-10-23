"""Hourly solar energy chain per TerraEnergy technical report (section 5).

Chain: NASA POWER hourly data -> pvlib solar position -> Hay-Davies POA
transposition -> Faiman cell temperature -> DC power with thermal derate ->
system losses -> inverter -> clipping -> PR / CF / P50/P75/P90 / solar score.
"""

import numpy as np
import pandas as pd
import pvlib

from datetime import datetime

from services.nasa_frame import (
    DAYS_PER_YEAR, HOURS_PER_YEAR, nasa_to_dataframe, interp_score,
)

_to_dataframe = nasa_to_dataframe
_interp_score = interp_score


def _hourly_times(start: datetime, end: datetime, tz=None) -> pd.DatetimeIndex:
    start = start.replace(minute=0, second=0, microsecond=0)
    end = end.replace(minute=0, second=0, microsecond=0)
    return pd.date_range(start=start, end=end, freq='h', tz=tz)


def _build_irradiance_series(df: pd.DataFrame) -> pd.DataFrame:
    """Reindex NASA hourly data on a continuous UTC hourly index.

    Hourly Wh/m2 per timestep is treated as W/m2 (standard hourly practice).
    Handles missing columns gracefully.
    """
    if df.empty:
        return pd.DataFrame()
    times = _hourly_times(df.index.min(), df.index.max(), tz=df.index.tz)
    out = df.reindex(times)
    
    # Handle irradiance columns - interpolate if present
    for col in ['ALLSKY_SFC_SW_DWN', 'ALLSKY_SFC_SW_DNI', 'ALLSKY_SFC_SW_DIFF',
                'CLRSKY_SFC_SW_DWN']:
        if col in out.columns:
            out[col] = out[col].interpolate(limit=4).fillna(0.0)
        else:
            # Create missing column with zeros (will be handled downstream)
            out[col] = 0.0
    
    for col in ['T2M', 'WS10M']:
        if col in out.columns:
            out[col] = out[col].ffill().bfill()
        else:
            # Default values
            out[col] = 25.0 if col == 'T2M' else 1.0
    return out


def _solar_precompute(
    data: dict,
    latitude: float,
    longitude: float,
) -> dict | None:
    """Build irradiance series + solar position once per location/time-range.

    Solar position depends only on time and coordinates, not on panel tilt or
    azimuth. Reusing it across the orientation search avoids recomputing the
    expensive pvlib solar positions tens of times.
    """
    df = _to_dataframe(data)
    if df.empty:
        return None

    s = _build_irradiance_series(df)
    if s.empty:
        return None

    solar_position = pvlib.solarposition.get_solarposition(
        s.index, latitude, longitude, method='nrel_numpy'
    )

    return {
        "s": s,
        "zen": solar_position['apparent_zenith'],
        "azi": solar_position['azimuth'],
        "dni_extra": pvlib.irradiance.get_extra_radiation(s.index),
    }


def _solar_hourly(
    data: dict,
    latitude: float,
    longitude: float,
    capacity_kw: float = 1000.0,
    tilt_deg: float | None = None,
    azimuth_deg: float | None = None,
    gamma_pmax_pct: float = -0.35,
    inverter_efficiency: float = 0.96,
    dc_ac_ratio: float = 1.2,
    soiling_loss: float = 0.025,
    wiring_loss: float = 0.02,
    mismatch_loss: float = 0.015,
    shading_loss: float = 0.005,
    availability: float = 0.99,
    albedo: float = 0.2,
    pre: dict | None = None,
) -> dict:
    """Run the full hourly solar chain. Returns arrays + aggregates.

    ``pre`` optionally carries the irradiance series + solar position computed
    once via :func:`_solar_precompute`; when omitted it is computed here.
    """
    if pre is None:
        pre = _solar_precompute(data, latitude, longitude)
    if pre is None:
        return {"error": "No data available"}

    s = pre["s"]
    zen = pre["zen"]
    azi = pre["azi"]
    dni_extra = pre["dni_extra"]

    if tilt_deg is None:
        tilt_deg = abs(latitude)
    if azimuth_deg is None:
        azimuth_deg = 180.0 if latitude >= 0 else 0.0

    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt_deg,
        surface_azimuth=azimuth_deg,
        solar_zenith=zen,
        solar_azimuth=azi,
        dni=s['ALLSKY_SFC_SW_DNI'],
        ghi=s['ALLSKY_SFC_SW_DWN'],
        dhi=s['ALLSKY_SFC_SW_DIFF'],
        dni_extra=dni_extra,
        model='haydavies',
        albedo=albedo,
    )['poa_global']

    t_air = s['T2M'] if 'T2M' in s.columns else pd.Series(25.0, index=s.index)
    wind = s['WS10M'] if 'WS10M' in s.columns else pd.Series(1.0, index=s.index)
    t_cell = pvlib.temperature.faiman(poa, t_air, wind)

    # DC power
    p_dc0 = capacity_kw * poa / 1000.0
    f_temp = np.clip(1 + (gamma_pmax_pct / 100.0) * (t_cell - 25.0), 0.0, 1.25)
    p_dc = p_dc0 * f_temp

    # System losses
    f_sys = ((1 - soiling_loss) * (1 - wiring_loss) * (1 - mismatch_loss)
             * (1 - shading_loss) * availability)

    # Inverter + clipping
    p_ac_raw = p_dc * f_sys * inverter_efficiency
    p_ac = np.minimum(p_ac_raw, capacity_kw / dc_ac_ratio)

    p_ac = pd.Series(p_ac, index=s.index)
    poa = pd.Series(poa, index=s.index)

    days_covered = (s.index.max() - s.index.min()).days + 1

    # Energy (kWh)
    sum_ac = float(p_ac.sum())
    e_ann = sum_ac * (DAYS_PER_YEAR / days_covered)

    # POA annual (kWh/m2)
    poa_kwh_m2 = float(poa.sum()) / 1000.0
    poa_ann_kwh_m2 = poa_kwh_m2 * (DAYS_PER_YEAR / days_covered)

    # Indicators
    specific_yield = e_ann / capacity_kw if capacity_kw > 0 else 0.0
    capacity_factor = e_ann / (capacity_kw * HOURS_PER_YEAR) if capacity_kw > 0 else 0.0
    performance_ratio = (
        sum_ac / (capacity_kw * poa_kwh_m2) if (capacity_kw > 0 and poa_kwh_m2 > 0) else 0.0
    )

    # Daily statistics
    daily = pd.DataFrame({'ghi': s['ALLSKY_SFC_SW_DWN'], 'ac': p_ac}).resample('D').sum()
    daily = daily[daily['ghi'] > 0]
    # Hourly values are Wh/m2 per hour == average W/m2; daily mean = mean * 24 h / 1000.
    ghi_daily_mean = float(s['ALLSKY_SFC_SW_DWN'].mean() * 24.0 / 1000.0)
    daily_cv = float(daily['ghi'].std() / daily['ghi'].mean()) if len(daily) > 1 and daily['ghi'].mean() > 0 else 0.0
    daily_ac = daily['ac']
    ac_cv = float(daily_ac.std() / daily_ac.mean()) if len(daily_ac) > 1 and daily_ac.mean() > 0 else 0.0

    # P50 / P75 / P90 (normal approximation, screening only)
    p50 = e_ann
    p75 = p50 * (1 - 0.674 * ac_cv)
    p90 = p50 * (1 - 1.282 * ac_cv)

    # Clarity index K = GHI / GHI_clear (empirical, over daylight)
    clear = s['CLRSKY_SFC_SW_DWN'] if 'CLRSKY_SFC_SW_DWN' in s.columns else s['ALLSKY_SFC_SW_DWN']
    mask = clear > 50
    if mask.any() and float(clear[mask].sum()) > 0:
        clarity_ratio = float(s['ALLSKY_SFC_SW_DWN'][mask].sum() / clear[mask].sum())
    else:
        clarity_ratio = 0.0

    # Temperature loss (mean, irradiance-weighted)
    w = poa > 50
    temp_loss = float((1 - f_temp[w]).mean() * 100) if w.any() else 0.0

    combined_loss = (
        1 - (1 - temp_loss / 100) * (1 - inverter_efficiency) * (1 - soiling_loss)
        * (1 - wiring_loss) * (1 - mismatch_loss) * (1 - shading_loss) * (1 - availability)
    ) * 100

    # Score (report 5.8): 0.50 GHI + 0.35 yield + 0.15 stability
    ghi_score = _interp_score(ghi_daily_mean, 2.5, 7.0)
    yield_score = _interp_score(specific_yield, 700.0, 2100.0)
    stab_score = 100.0 - _interp_score(daily_cv, 0.10, 0.60)
    score = 0.50 * ghi_score + 0.35 * yield_score + 0.15 * stab_score

    t_cell_mean = float(t_cell[poa > 50].mean()) if (poa > 50).any() else float(t_cell.mean())
    t_amb = float(s['T2M'].mean()) if 'T2M' in s.columns else 25.0

    return {
        "ac_hourly": p_ac.values,
        "poa_hourly": poa.values,
        "times": s.index,
        "ghi_daily_mean": ghi_daily_mean,
        "dni_mean": float(s['ALLSKY_SFC_SW_DNI'].mean()),
        "dhi_mean": float(s['ALLSKY_SFC_SW_DIFF'].mean()),
        "e_ann": e_ann,
        "sum_ac": sum_ac,
        "specific_yield": specific_yield,
        "capacity_factor": capacity_factor,
        "performance_ratio": performance_ratio,
        "p50": p50,
        "p75": p75,
        "p90": p90,
        "daily_cv": daily_cv,
        "clarity_ratio": clarity_ratio,
        "temp_loss": temp_loss,
        "t_cell_mean": t_cell_mean,
        "t_amb": t_amb,
        "score": min(100.0, max(0.0, score)),
        "poa_ann_kwh_m2": poa_ann_kwh_m2,
        "days_covered": days_covered,
    }


def _optimize_orientation(
    data: dict, latitude: float, longitude: float, config: dict,
    pre: dict | None = None,
) -> dict:
    """Search best tilt/azimuth (report 5.9) using the full hourly AC model."""
    hemisphere_az = 180.0 if latitude >= 0 else 0.0
    base = dict(config)
    base.pop('optimize_orientation', None)
    base.pop('tilt_deg', None)
    base.pop('azimuth_deg', None)

    if pre is None:
        pre = _solar_precompute(data, latitude, longitude)
    if pre is None:
        return {"optimized_tilt_deg": abs(latitude), "optimized_azimuth_deg": hemisphere_az, "orientation_scenarios": []}

    def energy(tilt: float, az: float) -> float:
        r = _solar_hourly(data, latitude, longitude, tilt_deg=tilt, azimuth_deg=az, pre=pre, **base)
        return r.get('e_ann', 0.0)

    best_tilt, best_az, best_e = 0.0, hemisphere_az, 0.0

    for tilt in range(0, 91, 5):
        e = energy(float(tilt), hemisphere_az)
        if e > best_e:
            best_tilt, best_az, best_e = float(tilt), hemisphere_az, e

    for tilt in np.arange(max(0, best_tilt - 4), min(90, best_tilt + 4) + 1, 1):
        e = energy(float(tilt), hemisphere_az)
        if e > best_e:
            best_tilt, best_az, best_e = float(tilt), hemisphere_az, e

    for az in range(int(hemisphere_az) - 60, int(hemisphere_az) + 61, 15):
        e = energy(best_tilt, float(az))
        if e > best_e:
            best_tilt, best_az, best_e = best_tilt, float(az), e

    for az in np.arange(best_az - 10, best_az + 11, 5):
        e = energy(best_tilt, float(az))
        if e > best_e:
            best_tilt, best_az, best_e = best_tilt, float(az), e

    scenarios = []
    for label, tilt, az in [
        ('HORIZONTAL', 0.0, hemisphere_az),
        ('LOW SLOPE', 10.0, hemisphere_az),
        ('LATITUDE', abs(latitude), hemisphere_az),
    ]:
        e = energy(tilt, az)
        scenarios.append({"label": label, "tilt_deg": tilt, "azimuth_deg": az, "energy_kwh": round(e, 0)})

    if config.get('tilt_deg') is not None:
        e = energy(config['tilt_deg'], config.get('azimuth_deg', hemisphere_az))
        scenarios.append({
            "label": "USER", "tilt_deg": config['tilt_deg'],
            "azimuth_deg": config.get('azimuth_deg', hemisphere_az), "energy_kwh": round(e, 0),
        })

    scenarios.append({"label": "OPTIMUM", "tilt_deg": round(best_tilt, 1), "azimuth_deg": round(best_az, 1), "energy_kwh": round(best_e, 0)})

    return {
        "optimized_tilt_deg": round(best_tilt, 1),
        "optimized_azimuth_deg": round(best_az, 1),
        "orientation_scenarios": scenarios,
    }


def _compute_monthly(series: pd.Series, per_day: bool = False) -> dict:
    monthly = {}
    for m in range(1, 13):
        part = series[series.index.month == m]
        if per_day:
            days = part.index.day
            if len(part) > 0:
                # Hourly values are Wh/m2 per hour; convert to kWh/m2/day.
                val = float(part.sum()) / 1000.0 / max(1, days.max())
            else:
                val = 0.0
        else:
            val = float(part.mean()) if len(part) > 0 else 0.0
        monthly[str(m)] = round(val, 2)
    return monthly


def analyze_solar(
    data: dict,
    latitude: float = 33.5,
    longitude: float = 0.0,
    capacity_kw: float = 1000.0,
    tilt_deg: float | None = None,
    azimuth_deg: float | None = None,
    gamma_pmax_pct: float = -0.35,
    inverter_efficiency: float = 0.96,
    dc_ac_ratio: float = 1.2,
    soiling_loss: float = 0.025,
    wiring_loss: float = 0.02,
    mismatch_loss: float = 0.015,
    shading_loss: float = 0.005,
    availability: float = 0.99,
    albedo: float = 0.2,
    optimize_orientation: bool = False,
) -> dict:
    """Full hourly solar analysis returning the public result dict."""
    config = {
        "capacity_kw": capacity_kw,
        "gamma_pmax_pct": gamma_pmax_pct,
        "inverter_efficiency": inverter_efficiency,
        "dc_ac_ratio": dc_ac_ratio,
        "soiling_loss": soiling_loss,
        "wiring_loss": wiring_loss,
        "mismatch_loss": mismatch_loss,
        "shading_loss": shading_loss,
        "availability": availability,
        "albedo": albedo,
    }

    pre = _solar_precompute(data, latitude, longitude)

    r = _solar_hourly(
        data, latitude, longitude,
        tilt_deg=tilt_deg, azimuth_deg=azimuth_deg, **config, pre=pre,
    )
    if r.get("error"):
        return r

    s = pre["s"] if pre is not None else pd.DataFrame()

    opt = {}
    if optimize_orientation:
        opt = _optimize_orientation(data, latitude, longitude, {
            **config, "tilt_deg": tilt_deg, "azimuth_deg": azimuth_deg,
        }, pre=pre)

    losses = {
        "temperature": round(r["temp_loss"], 2),
        "inverter": round((1 - inverter_efficiency) * 100, 2),
        "wiring": round(wiring_loss * 100, 2),
        "soiling": round(soiling_loss * 100, 2),
        "mismatch": round(mismatch_loss * 100, 2),
        "shading": round(shading_loss * 100, 2),
        "availability": round((1 - availability) * 100, 2),
        "total": round((
            1 - (1 - r["temp_loss"] / 100) * inverter_efficiency * (1 - soiling_loss)
            * (1 - wiring_loss) * (1 - mismatch_loss) * (1 - shading_loss) * availability
        ) * 100, 2),
    }

    if r["ghi_daily_mean"] >= 6.0:
        resource_class = "Excellent"
    elif r["ghi_daily_mean"] >= 5.0:
        resource_class = "Very Good"
    elif r["ghi_daily_mean"] >= 4.0:
        resource_class = "Good"
    elif r["ghi_daily_mean"] >= 3.0:
        resource_class = "Moderate"
    else:
        resource_class = "Poor"

    result = {
        "ghi_avg": round(r["ghi_daily_mean"], 2),
        "dni_avg": round(r["dni_mean"], 2),
        "dhi_avg": round(r["dhi_mean"], 2),
        "capacity_kw": capacity_kw,
        "tilt_deg": round(tilt_deg if tilt_deg is not None else abs(latitude), 1),
        "azimuth_deg": round(azimuth_deg if azimuth_deg is not None else (180.0 if latitude >= 0 else 0.0), 1),
        "capacity_factor": round(r["capacity_factor"], 4),
        "performance_ratio": round(r["performance_ratio"], 4),
        "specific_yield_kwh_kwp": round(r["specific_yield"], 1),
        "annual_energy_kwh": round(r["sum_ac"], 1),
        "annual_energy_corrected_kwh": round(r["e_ann"], 1),
        "p50_annual_kwh": round(r["p50"], 1),
        "p75_annual_kwh": round(r["p75"], 1),
        "p90_annual_kwh": round(r["p90"], 1),
        "score": round(r["score"], 1),
        "variability": round(r["daily_cv"], 3),
        "poa_irradiance": round(r["poa_ann_kwh_m2"], 2),
        "poa_annual_kwh_m2": round(r["poa_ann_kwh_m2"], 2),
        "temperature_loss_pct": round(r["temp_loss"], 2),
        "t_cell_estimated": round(r["t_cell_mean"], 1),
        "t_ambient_avg": round(r["t_amb"], 1),
        "clarity_ratio": round(r["clarity_ratio"], 3),
        "resource_class": resource_class,
        "losses_breakdown": losses,
        "monthly_ghi": _compute_monthly(s['ALLSKY_SFC_SW_DWN'], per_day=True),
        "monthly_dni": _compute_monthly(s['ALLSKY_SFC_SW_DNI'], per_day=True),
        "monthly_dhi": _compute_monthly(s['ALLSKY_SFC_SW_DIFF'], per_day=True),
        "days_covered": r["days_covered"],
    }
    result.update(opt)
    return result


def solar_hourly_series(data: dict, latitude: float, longitude: float,
                        capacity_kw: float = 1000.0,
                        tilt_deg: float | None = None,
                        azimuth_deg: float | None = None,
                        inverter_efficiency: float = 0.96,
                        dc_ac_ratio: float = 1.2) -> pd.Series:
    """Return hourly AC series (kWh) for hybrid complementarity."""
    r = _solar_hourly(
        data, latitude, longitude,
        capacity_kw=capacity_kw, tilt_deg=tilt_deg, azimuth_deg=azimuth_deg,
        inverter_efficiency=inverter_efficiency, dc_ac_ratio=dc_ac_ratio,
    )
    if r.get("error"):
        return pd.Series(dtype=float)
    return pd.Series(r["ac_hourly"], index=r["times"])
