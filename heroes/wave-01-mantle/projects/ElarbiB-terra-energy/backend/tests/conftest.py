"""Shared fixtures for the TerraEnergy backend test-suite."""

import numpy as np
import pandas as pd
import pytest

HOURS = pd.date_range('2023-01-01 00:00', periods=24 * 31, freq='h', tz='UTC')


def _param(series):
    return {d.strftime('%Y%m%d%H'): round(float(v), 4) if np.isfinite(v) else -999.0
            for d, v in zip(HOURS, series)}


@pytest.fixture(scope="session")
def nasa_data() -> dict:
    """Synthetic NASA POWER hourly dataset for Casablanca, January 2023."""
    hour = HOURS.hour.values.astype(float)

    # Diurnal GHI (Wh/m2 per hour ~ W/m2), daylight ~ 7h-19h
    daylight = np.clip(np.sin(np.pi * (hour - 6.0) / 12.0), 0.0, 1.0)
    ghi = 820.0 * daylight * (1.0 + 0.15 * np.sin(2 * np.pi * np.arange(len(HOURS)) / 24.0 * 0.13))
    dni = 0.68 * ghi * (1.0 + 0.05 * np.sin(np.arange(len(HOURS))))
    dhi = np.clip(ghi - dni * daylight, 5.0, 400.0)

    t2m = 24.0 + 4.0 * np.sin(2 * np.pi * (hour - 13.0) / 24.0)
    ws10 = 3.5 + 1.5 * np.sin(2 * np.pi * hour / 24.0)
    ws50 = 6.5 + 2.0 * np.sin(2 * np.pi * hour / 24.0)
    wd50 = 270.0 + 20.0 * np.sin(np.arange(len(HOURS)) / 30.0)
    ps = 1015.0 + 5.0 * np.sin(2 * np.pi * np.arange(len(HOURS)) / 300.0)

    return {
        "properties": {
            "parameter": {
                "ALLSKY_SFC_SW_DWN": _param(ghi),
                "ALLSKY_SFC_SW_DNI": _param(dni),
                "ALLSKY_SFC_SW_DIFF": _param(dhi),
                "T2M": _param(t2m),
                "WS10M": _param(ws10),
                "WS50M": _param(ws50),
                "WD50M": _param(wd50),
                "PS": _param(ps),
            }
        }
    }
