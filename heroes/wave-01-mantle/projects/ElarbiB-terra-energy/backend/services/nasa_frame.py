"""Shared NASA POWER parsing helpers and scoring utilities.

Used by solar_analysis, wind_analysis and hybrid_analysis.
"""

import numpy as np
import pandas as pd

DAYS_PER_YEAR = 365.25
HOURS_PER_YEAR = DAYS_PER_YEAR * 24  # 8766


def nasa_to_dataframe(data: dict) -> pd.DataFrame:
    """Flatten a NASA POWER JSON response into a datetime-indexed DataFrame.

    Missing values (-999.0) become NaN. Handles both hourly (%Y%m%d%H)
    and daily/monthly (%Y%m%d) date keys.
    """
    props = data.get('properties', {})
    parameters = props.get('parameter', {})
    if not parameters:
        return pd.DataFrame()

    first_key = list(parameters.keys())[0]
    dates = list(parameters[first_key].keys())

    df = pd.DataFrame({'date': dates})
    for param_name, values in parameters.items():
        df[param_name] = [values.get(d, np.nan) for d in dates]

    df = df.replace(-999.0, np.nan)

    sample = str(dates[0]) if dates else ''
    if len(sample) >= 10:
        df['dt'] = pd.to_datetime(df['date'], format='%Y%m%d%H', errors='coerce')
    else:
        df['dt'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
    df = df.dropna(subset=['dt']).sort_values('dt').set_index('dt')
    return df.drop(columns=['date'])


def dataframe_to_nasa_format(df: pd.DataFrame) -> dict:
    """Convert standardized DataFrame to NASA POWER response format.
    
    Standard columns: ghi, dni, dhi, ws, wd, t2m, rh, ps, ws2m, ws10m, ws50m, wd50m, u10m, v10m, u50m, v50m, rhoa
    """
    param_map = {
        "ghi": "ALLSKY_SFC_SW_DWN",
        "dni": "ALLSKY_SFC_SW_DNI",
        "dhi": "ALLSKY_SFC_SW_DIFF",
        "ws": "WS10M",
        "ws50m": "WS50M",
        "wd": "WD50M",
        "wd50m": "WD50M",
        "t2m": "T2M",
        "rh": "RH2M",
        "ps": "PS",
        "ws2m": "WS2M",
        "ws10m": "WS10M",
        "u10m": "U10M",
        "v10m": "V10M",
        "u50m": "U50M",
        "v50m": "V50M",
        "rhoa": "RHOA",
    }
    
    result = {"properties": {"parameter": {}}}
    
    for std_col, nasa_param in param_map.items():
        if std_col in df.columns:
            series = df[std_col].dropna()
            data_dict = {}
            for idx, val in series.items():
                if hasattr(idx, 'strftime'):
                    date_str = idx.strftime("%Y%m%d%H")
                else:
                    date_str = str(idx)
                data_dict[date_str] = float(val) if val is not None else -999.0
            result["properties"]["parameter"][nasa_param] = data_dict
    
    # Also map ws -> WS50M if ws50m not present (extrapolate from 10m)
    if "ws" in df.columns and "ws50m" not in df.columns:
        series = df["ws"].dropna()
        data_dict = {}
        for idx, val in series.items():
            if hasattr(idx, 'strftime'):
                date_str = idx.strftime("%Y%m%d%H")
            else:
                date_str = str(idx)
            # Rough extrapolation: WS50M ≈ WS10M * (50/10)^0.14
            data_dict[date_str] = float(val * 1.3) if val is not None else -999.0
        result["properties"]["parameter"]["WS50M"] = data_dict
    
    # Also map wd -> WD50M if wd50m not present
    if "wd" in df.columns and "wd50m" not in df.columns:
        series = df["wd"].dropna()
        data_dict = {}
        for idx, val in series.items():
            if hasattr(idx, 'strftime'):
                date_str = idx.strftime("%Y%m%d%H")
            else:
                date_str = str(idx)
            data_dict[date_str] = float(val) if val is not None else -999.0
        result["properties"]["parameter"]["WD50M"] = data_dict
    
    return result


def reindex_hourly(df: pd.DataFrame, fill: str = 'interpolate') -> pd.DataFrame:
    """Reindex on a continuous UTC hourly range and fill gaps."""
    if df.empty:
        return pd.DataFrame()
    times = pd.date_range(
        start=df.index.min().replace(minute=0, second=0, microsecond=0),
        end=df.index.max().replace(minute=0, second=0, microsecond=0),
        freq='h', tz=df.index.tz,
    )
    out = df.reindex(times)
    for col in out.columns:
        if fill == 'interpolate':
            out[col] = out[col].interpolate(limit=4).ffill().bfill()
        else:
            out[col] = out[col].ffill().bfill()
    return out


def interp_score(x: float, x_lo: float, x_hi: float) -> float:
    """Linear interpolation of a metric to a 0-100 score."""
    if x <= x_lo:
        return 0.0
    if x >= x_hi:
        return 100.0
    return (x - x_lo) / (x_hi - x_lo) * 100.0
