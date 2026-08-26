"""Read-only inventory and research helpers for the Autono demo.

``data/source/cars.json`` is the Rasa Motors inventory. ``search_results.json``
stands in for a web research index — it lets the agent quote review snippets
without calling out to a live search API during a demo.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

SOURCE_PATH = Path(__file__).resolve().parent.parent / "data" / "source"


@lru_cache(maxsize=1)
def load_cars() -> List[Dict[str, Any]]:
    """Return the full dealership inventory."""
    with open(SOURCE_PATH / "cars.json", "r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=1)
def load_search_results() -> List[Dict[str, Any]]:
    """Return the canned research articles used for recommendations."""
    with open(SOURCE_PATH / "search_results.json", "r", encoding="utf-8") as file:
        return json.load(file)


def list_dealers() -> List[str]:
    """Every dealer that has at least one car in stock."""
    return sorted({car["dealer_location"] for car in load_cars()})


def list_types() -> List[str]:
    """Every body type present in the inventory."""
    return sorted({car["type"] for car in load_cars()})


def _matches(car: Dict[str, Any], needle: str, field: str) -> bool:
    return needle.lower().strip() in str(car.get(field, "")).lower()


def search_inventory(
    model: Optional[str] = None,
    dealer: Optional[str] = None,
    car_type: Optional[str] = None,
    new_or_used: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Filter the inventory. Every filter is optional and case-insensitive."""
    results = load_cars()

    if model:
        results = [car for car in results if _matches(car, model, "model")]
    if dealer:
        results = [car for car in results if _matches(car, dealer, "dealer_location")]
    if car_type:
        results = [car for car in results if _matches(car, car_type, "type")]
    if new_or_used:
        wanted = new_or_used.lower().strip()
        results = [car for car in results if str(car.get("new_or_used", "")).lower() == wanted]
    if max_price is not None:
        results = [car for car in results if float(car["price"]) <= float(max_price)]
    if min_price is not None:
        results = [car for car in results if float(car["price"]) >= float(min_price)]

    results = sorted(results, key=lambda car: float(car["price"]))
    return results[:limit] if limit else results


def find_similar(model: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Cars of the same body type in a comparable price band.

    Falls back to the closest cars by price when the model is unknown, so the
    agent always has something concrete to offer.
    """
    matches = search_inventory(model=model, limit=1)
    if not matches:
        return []

    reference = matches[0]
    price = float(reference["price"])
    low, high = price * 0.75, price * 1.25

    candidates = [
        car
        for car in load_cars()
        if car["model"] != reference["model"]
        and car["type"] == reference["type"]
        and low <= float(car["price"]) <= high
    ]
    if not candidates:
        candidates = [car for car in load_cars() if car["model"] != reference["model"]]

    candidates.sort(key=lambda car: abs(float(car["price"]) - price))
    return candidates[:limit]


def list_dealers_for_model(model: str) -> List[Dict[str, Any]]:
    """Which dealers hold a given model, with price and condition."""
    return [
        {
            "dealer_name": car["dealer_location"],
            "model": car["model"],
            "price": float(car["price"]),
            "new_or_used": car["new_or_used"],
        }
        for car in load_cars()
        if _matches(car, model, "model")
    ]


def get_search_snippets(query: str, limit: int = 3) -> List[Dict[str, str]]:
    """Rank the canned research articles against a free-text query.

    Scoring is a simple token overlap over title and body — enough to surface
    a relevant review for a model, body type, or budget question.
    """
    tokens = [token for token in query.lower().replace(",", " ").split() if len(token) > 2]
    if not tokens:
        return []

    scored = []
    for article in load_search_results():
        haystack = f"{article['title']} {article['content']}".lower()
        title = article["title"].lower()
        score = sum(haystack.count(token) + (3 if token in title else 0) for token in tokens)
        if score:
            scored.append((score, article))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {
            "title": article["title"],
            "url": article["url"],
            "summary": article["content"][:400],
        }
        for _, article in scored[:limit]
    ]
