"""Equipment catalog per TerraEnergy report (section 4).

pvlib pvsystem.retrieve_sam loads the CEC/SAM module and inverter databases.
Sizing follows report 4.2: S_util = S_available * f_occupation,
N_modules = floor(S_util / S_module), P_dc [kWp] = N * P_module / 1000.
"""

import functools
import math

import pvlib

from services.geospatial import INSTALLATION_TYPES

_MODULES_CACHE = None
_INVERTERS_CACHE = None


def _load_modules():
    global _MODULES_CACHE
    if _MODULES_CACHE is None:
        _MODULES_CACHE = pvlib.pvsystem.retrieve_sam("CECMod")
    return _MODULES_CACHE


def _load_inverters():
    global _INVERTERS_CACHE
    if _INVERTERS_CACHE is None:
        _INVERTERS_CACHE = pvlib.pvsystem.retrieve_sam("CECInverter")
    return _INVERTERS_CACHE


def _row_to_module(name: str, row) -> dict:
    def val(col):
        try:
            return float(row.get(col, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    power_w = val("STC")
    area_m2 = val("A_c")
    eff = power_w / (area_m2 * 1000.0) * 100.0 if area_m2 > 0 else 0.0
    return {
        "name": name,
        "power_w": round(power_w, 1),
        "area_m2": round(area_m2, 4),
        "efficiency_pct": round(eff, 2),
        "temperature_coefficient_pct_c": val("gamma_r"),
    }


def _row_to_inverter(name: str, row) -> dict:
    def val(col):
        try:
            return float(row.get(col, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    paco = val("Paco")
    pdco = val("Pdco")
    return {
        "name": name,
        "pac_w": round(paco, 1),
        "pdc_w": round(pdco, 1),
        "efficiency_pct": round(min(100.0, paco / pdco * 100.0), 2) if pdco > 0 else 0.0,
    }


@functools.lru_cache(maxsize=1)
def get_modules(limit: int = 50, query: str | None = None, min_power_w: float = 0.0) -> list[dict]:
    df = _load_modules()
    modules = []
    for name in df.columns:
        m = _row_to_module(name, df[name])
        if m["power_w"] < min_power_w:
            continue
        if query and query.lower() not in name.lower():
            continue
        modules.append(m)
    modules.sort(key=lambda x: -x["power_w"])
    return modules[:limit]


@functools.lru_cache(maxsize=1)
def get_inverters(limit: int = 50, query: str | None = None, min_pac_w: float = 0.0) -> list[dict]:
    df = _load_inverters()
    inverters = []
    for name in df.columns:
        inv = _row_to_inverter(name, df[name])
        if inv["pac_w"] < min_pac_w:
            continue
        if query and query.lower() not in name.lower():
            continue
        inverters.append(inv)
    inverters.sort(key=lambda x: -x["pac_w"])
    return inverters[:limit]


def propose_system(
    area_m2: float,
    support: str = "roof",
    module_name: str | None = None,
    inverter_name: str | None = None,
) -> dict:
    support = support if support in INSTALLATION_TYPES else "roof"
    f_occupation = INSTALLATION_TYPES[support]["occupation_factor"]

    modules = get_modules(limit=10)
    if not modules:
        return {"error": "Aucun module CEC disponible"}

    if module_name:
        selected = next((m for m in modules if m["name"] == module_name), None)
    else:
        selected = next((m for m in modules if m["power_w"] >= 300), None) or modules[0]
    if not selected:
        selected = modules[0]

    s_util = area_m2 * f_occupation
    n_modules = int(s_util // selected["area_m2"]) if selected["area_m2"] > 0 else 0
    p_dc_kwp = round(n_modules * selected["power_w"] / 1000.0, 2)

    inverters = get_inverters(limit=30)
    inverter = None
    n_inverters = 0
    if p_dc_kwp > 0 and inverters:
        if inverter_name:
            candidate = next((i for i in inverters if i["name"] == inverter_name), None)
            if candidate:
                inverter = candidate
                n_inverters = max(1, math.ceil(p_dc_kwp * 1000.0 / inverter["pac_w"]))
        if inverter is None:
            for inv in sorted(inverters, key=lambda x: x["pac_w"]):
                if inv["pac_w"] >= p_dc_kwp * 1000.0:
                    inverter = inv
                    n_inverters = 1
                    break
            if inverter is None and inverters:
                inverter = max(inverters, key=lambda x: x["pac_w"])
                n_inverters = math.ceil(p_dc_kwp * 1000.0 / inverter["pac_w"])

    return {
        "installation_type": support,
        "installation_label": INSTALLATION_TYPES[support]["label"],
        "occupation_factor": f_occupation,
        "available_area_m2": round(area_m2, 1),
        "usable_area_m2": round(s_util, 1),
        "module": selected,
        "n_modules": n_modules,
        "proposed_kw": p_dc_kwp,
        "inverter": inverter,
        "n_inverters": n_inverters,
        "warning": "Facteurs d'occupation indicatifs : un plan d'implantation est nécessaire. "
                   "Proposez, puis cliquez sur « Appliquer ».",
    }

