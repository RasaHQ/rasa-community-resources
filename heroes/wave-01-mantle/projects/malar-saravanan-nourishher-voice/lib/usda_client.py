"""Thin async client for the USDA FoodData Central (FDC) search API.

Real external nutrient data — no seeded/fabricated food dataset. Free API,
no signup required for light use: the shared "DEMO_KEY" documented at
https://fdc.nal.usda.gov/api-key-signup works for the search endpoint used
here, though it is rate-limited; set USDA_FDC_API_KEY for a personal key.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# SR Legacy / Foundation / Survey (FNDDS) — the three dataTypes this client
# queries — all report nutrients per 100 g of the food, not per serving.
# Surfaced explicitly in every result so a meal plan can state real
# quantities rather than bare per-food numbers.
NUTRIENT_BASIS = "per 100 g"

# Macro/energy nutrients, always shown first and never %DV-less.
MACROS = {
    "Energy",
    "Protein",
    "Total lipid (fat)",
    "Carbohydrate, by difference",
    "Fiber, total dietary",
    "Total Sugars",
    "Sugars, total including NLEA",
}

# Condition-relevant micronutrients: thyroid (iodine, selenium), PCOS/fertility
# (folate, zinc, vitamin D, magnesium), general electrolyte/mineral status
# (sodium, potassium, calcium, iron) — calcium/iron doubling as the exact
# levothyroxine food-timing interaction this project's flagship skill covers.
MICROS = {
    "Sodium, Na",
    "Potassium, K",
    "Calcium, Ca",
    "Iron, Fe",
    "Zinc, Zn",
    "Magnesium, Mg",
    "Iodine, I",
    "Selenium, Se",
    "Folate, total",
    "Folic acid",
    "Vitamin D (D2 + D3)",
    "Vitamin B-12",
}

NUTRIENTS_OF_INTEREST = MACROS | MICROS

# FDA adult general-population Daily Values (2020 label update, 2000 kcal
# diet) — a real, published reference, not an LLM guess. (amount, unit) must
# match FDC's own unit strings for the same nutrient so %DV division is
# unit-consistent. No DV exists for total/added sugars, so none is listed —
# the tool reports the gram amount only, per the FDA's own labeling rules.
DAILY_VALUES: Dict[str, tuple[float, str]] = {
    "Energy": (2000, "KCAL"),
    "Protein": (50, "G"),
    "Total lipid (fat)": (78, "G"),
    "Carbohydrate, by difference": (275, "G"),
    "Fiber, total dietary": (28, "G"),
    "Sodium, Na": (2300, "MG"),
    "Potassium, K": (4700, "MG"),
    "Calcium, Ca": (1300, "MG"),
    "Iron, Fe": (18, "MG"),
    "Zinc, Zn": (11, "MG"),
    "Magnesium, Mg": (420, "MG"),
    "Iodine, I": (150, "UG"),
    "Selenium, Se": (55, "UG"),
    "Folate, total": (400, "UG"),
    "Folic acid": (400, "UG"),
    "Vitamin D (D2 + D3)": (20, "UG"),
    "Vitamin B-12": (2.4, "UG"),
}


class USDALookupError(RuntimeError):
    """Raised when the FDC API call fails or is misconfigured."""


def _api_key() -> str:
    return os.getenv("USDA_FDC_API_KEY", "DEMO_KEY").strip() or "DEMO_KEY"


def _percent_dv(name: str, value: Optional[float], unit: Optional[str]) -> Optional[float]:
    """Return %DV rounded to the nearest whole percent, or None if not computable."""
    dv = DAILY_VALUES.get(name)
    if dv is None or value is None or unit is None:
        return None
    dv_amount, dv_unit = dv
    if unit.upper() != dv_unit:
        return None
    return round((value / dv_amount) * 100)


def _extract_nutrients(food: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return macro/micro nutrients for *food*, each with value, unit, and %DV.

    Grouped under "macros" and "micros" so a skill can render a clearly
    separated table instead of one flat list.
    """
    macros: Dict[str, Dict[str, Any]] = {}
    micros: Dict[str, Dict[str, Any]] = {}
    for entry in food.get("foodNutrients", []):
        name = entry.get("nutrientName")
        if name not in NUTRIENTS_OF_INTEREST:
            continue
        bucket = macros if name in MACROS else micros
        if name in bucket:
            continue
        value = entry.get("value")
        unit = entry.get("unitName")
        bucket[name] = {
            "value": value,
            "unit": unit,
            "percent_daily_value": _percent_dv(name, value, unit),
        }
    return {"macros": macros, "micros": micros}


async def search_food(query: str, page_size: int = 3) -> Dict[str, Any]:
    """Search FDC for a food and return the top matches with macro/micro nutrients.

    Args:
        query: Free-text food description, e.g. "steel cut oats".
        page_size: Number of candidate matches to return.
    """
    params = {
        "api_key": _api_key(),
        "query": query,
        "pageSize": page_size,
        "dataType": ["SR Legacy", "Foundation", "Survey (FNDDS)"],
    }
    # The FDC gateway intermittently returns a bare 400 (no JSON body) for an
    # otherwise-valid request — reproduced directly against api.nal.usda.gov,
    # independent of api key or pageSize. One retry clears it in practice.
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(FDC_SEARCH_URL, params=params)
                response.raise_for_status()
                payload = response.json()
            break
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code == 400 and attempt == 0:
                continue
            raise USDALookupError(
                f"FDC API returned {exc.response.status_code} for query {query!r}"
            ) from exc
        except httpx.HTTPError as exc:
            raise USDALookupError(f"FDC API request failed for query {query!r}: {exc}") from exc
    else:
        raise USDALookupError(
            f"FDC API returned 400 twice for query {query!r}"
        ) from last_exc

    foods: List[Dict[str, Any]] = payload.get("foods", [])
    if not foods:
        return {"query": query, "basis": NUTRIENT_BASIS, "matches": []}

    matches = [
        {
            "description": food.get("description"),
            "fdc_id": food.get("fdcId"),
            **_extract_nutrients(food),
        }
        for food in foods
    ]
    return {"query": query, "basis": NUTRIENT_BASIS, "matches": matches}
