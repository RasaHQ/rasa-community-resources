"""Geospatial layer per TerraEnergy report (section 3).

Routing: IGN Geoplateforme (France), PDOK (Netherlands), Nominatim for
address geocoding, and OpenStreetMap Overpass as the worldwide parcel
fallback (building footprints / land-use parcels) for every other country.
Area is computed on the WGS84 sphere with R = 6378137 m (report 3.4).
"""

import math
import asyncio
import re
import httpx

R_WGS84 = 6378137.0

IGN_GEOCODE = "https://data.geopf.fr/geocodage/search/"
IGN_WFS = "https://data.geopf.fr/wfs/ows"
IGN_BUILDING_LAYER = "BDTOPO_V3:batiment"
PDOK_GEOCODE = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
PDOK_PARCEL = "https://api.pdok.nl/kadaster/brk-kadastrale-kaart/ogc/v1/collections/perceel/items"
NOMINATIM = "https://nominatim.openstreetmap.org/search"

OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

_TIMEOUT = httpx.Timeout(20.0)
_OVERPASS_TIMEOUT = httpx.Timeout(25.0)
_NOMINATIM_HEADERS = {
    "User-Agent": "TerraEnergy/1.0 (educational renewable-energy platform; "
                  "contact: contact@example.com)",
}
_HEADERS = _NOMINATIM_HEADERS

INSTALLATION_TYPES = {
    "roof": {"label": "Toiture / hangar", "occupation_factor": 0.72},
    "carport": {"label": "Ombrière", "occupation_factor": 0.60},
    "ground": {"label": "Sol / pompage", "occupation_factor": 0.45},
    "agrivoltaic": {"label": "Agrivoltaïsme", "occupation_factor": 0.25},
    "floating": {"label": "Flottant", "occupation_factor": 0.55},
}


def detect_country(lat: float, lon: float) -> str:
    if _in_france(lat, lon):
        return "france"
    if _in_netherlands(lat, lon):
        return "netherlands"
    if 27.5 <= lat <= 36.0 and -17.5 <= lon <= -1.0:
        return "morocco"
    return "other"


def _point_in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        c1 = ring[i]
        c2 = ring[(i + 1) % n]
        x1, y1 = c1[0], c1[1]
        x2, y2 = c2[0], c2[1]
        if (y1 > y) != (y2 > y):
            x_int = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_int:
                inside = not inside
    return inside


def point_in_polygon(x: float, y: float, geometry: dict) -> bool:
    """Handles Point, Polygon (with holes) and MultiPolygon."""
    if geometry.get("type") == "MultiPolygon":
        for poly in geometry["coordinates"]:
            if point_in_polygon(x, y, {"type": "Polygon", "coordinates": poly}):
                return True
        return False

    coords = geometry.get("coordinates") or []
    if geometry.get("type") == "Polygon" and coords:
        if not _point_in_ring(x, y, coords[0]):
            return False
        for hole in coords[1:]:
            if _point_in_ring(x, y, hole):
                return False
        return True
    return False


def geojson_area_m2(geometry: dict) -> float:
    """Geodesic area on sphere (report 3.4), in square metres."""
    coords = geometry.get("coordinates") or []
    rings = []
    if geometry.get("type") == "Polygon":
        rings = coords
    elif geometry.get("type") == "MultiPolygon":
        rings = [ring for poly in coords for ring in poly]
    else:
        return 0.0

    total = 0.0
    for ring in rings:
        n = len(ring)
        if n < 3:
            continue
        a = 0.0
        for i in range(n - 1):
            lon1, lat1 = ring[i][0], ring[i][1]
            lon2, lat2 = ring[i + 1][0], ring[i + 1][1]
            dlon = math.radians(lon2 - lon1)
            a += dlon * (2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
        total += abs(a)
    return abs(R_WGS84 ** 2 / 2.0 * total)


def _in_france(lat: float, lon: float) -> bool:
    return 41.0 <= lat <= 51.2 and -5.5 <= lon <= 9.5


def _in_netherlands(lat: float, lon: float) -> bool:
    return 50.75 <= lat <= 53.6 and 3.2 <= lon <= 7.3


def geocode_fallback_queries(query: str) -> list[str]:
    """Progressive simplifications of an address for fuzzy geocoding.

    Order: full query, without the leading house number, without numeric
    street tokens, with 'QU' -> 'Quartier' expanded, then with common street
    words stripped so the neighbourhood/city part can still be found."""
    candidates: list[str] = []

    def add(q: str) -> None:
        q = " ".join(q.split())
        if q and q not in candidates:
            candidates.append(q)

    def strip_numbers(q: str) -> str:
        return " ".join(re.sub(r"\b\d+\b", "", q).split())

    STREET_WORDS = r"\b(rue|rues|avenue|ave|av|boulevard|bd|boul|route|street|st|str|road|sq|place|allée|allee)\b"

    add(query)

    m = re.match(r"^\s*\d+\s+(.*)$", query)
    if m:
        add(m.group(1))

    add(strip_numbers(query))

    expanded = re.sub(r"\bQU\b", "Quartier", query, flags=re.IGNORECASE)
    if expanded != query:
        add(expanded)
        m = re.match(r"^\s*\d+\s+(.*)$", expanded)
        if m:
            add(m.group(1))
        add(strip_numbers(expanded))
    else:
        expanded = query

    streetless = strip_numbers(re.sub(STREET_WORDS, "", expanded, flags=re.IGNORECASE))
    add(streetless)

    tokens = streetless.split()
    if len(tokens) > 2:
        add(" ".join(tokens[1:]))
    return candidates


async def geocode(query: str, country: str | None = None) -> list[dict]:
    """Country-aware geocoding. When country is known, use the national
    provider first (IGN/PDOK). Otherwise Nominatim is the global fallback,
    enriched by the national provider when the result lies in France/NL.
    Nominatim retries with progressively simpler forms of the address."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:

        async def _nominatim(q: str):
            r = await client.get(
                NOMINATIM,
                params={"q": q, "format": "jsonv2", "limit": 5, "accept-language": "fr", "email": "contact@example.com"},
                headers=_NOMINATIM_HEADERS,
            )
            r.raise_for_status()
            return [
                {
                    "label": d.get("display_name", ""),
                    "latitude": float(d["lat"]),
                    "longitude": float(d["lon"]),
                    "country": detect_country(float(d["lat"]), float(d["lon"])),
                    "source": "Nominatim",
                }
                for d in r.json()
            ]

        async def _ign():
            r = await client.get(IGN_GEOCODE, params={"q": query, "limit": 5})
            r.raise_for_status()
            results = []
            for f in r.json().get("features", []):
                props = f.get("properties", {})
                geom = f.get("geometry", {})
                if geom.get("type") != "Point":
                    continue
                lon, lat = geom["coordinates"]
                if not _in_france(lat, lon):
                    continue
                results.append({
                    "label": props.get("fullText") or props.get("name", ""),
                    "latitude": lat,
                    "longitude": lon,
                    "country": "france",
                    "source": "IGN",
                })
            return results

        async def _pdok():
            r = await client.get(
                PDOK_GEOCODE,
                params={"q": query, "rows": 5, "fl": "id,weergavenaam,centroide_ll"},
            )
            r.raise_for_status()
            results = []
            for d in r.json().get("response", {}).get("docs", []):
                c = d.get("centroide_ll", "")
                parts = c.replace("POINT(", "").replace(")", "").split()
                if len(parts) < 2:
                    continue
                lat, lon = float(parts[1]), float(parts[0])
                if not _in_netherlands(lat, lon):
                    continue
                results.append({
                    "label": d.get("weergavenaam", ""),
                    "latitude": lat,
                    "longitude": lon,
                    "country": "netherlands",
                    "source": "PDOK",
                })
            return results

        try:
            if country == "france":
                return (await _ign()) or await _nominatim(query)
            if country == "netherlands":
                return (await _pdok()) or await _nominatim(query)

            results: list[dict] = []
            for candidate in geocode_fallback_queries(query):
                try:
                    results = await _nominatim(candidate)
                except Exception:
                    results = []
                if results:
                    break
            if not results:
                return []

            top = results[0]
            try:
                if top["country"] == "france":
                    return (await _ign()) or results
                if top["country"] == "netherlands":
                    return (await _pdok()) or results
            except Exception:
                pass
            return results
        except Exception:
            return []


def _feature_containing_point(features: list, lon: float, lat: float) -> dict | None:
    for f in features:
        if point_in_polygon(lon, lat, f.get("geometry", {})):
            return f
    return None


async def get_parcel(lat: float, lon: float, radius_m: float = 200.0) -> dict:
    country = detect_country(lat, lon)
    if country == "france":
        return await _parcel_france(lat, lon, radius_m)
    if country == "netherlands":
        return await _parcel_netherlands(lat, lon, radius_m)
    return await _parcel_overpass(lat, lon, radius_m)


def _overpass_ring(nodes: list) -> list:
    """Overpass 'out geom' nodes ([{lat,lon},...]) -> closed [[lon,lat],...] ring."""
    if not nodes:
        return []
    ring = [[float(n["lon"]), float(n["lat"])] for n in nodes]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def overpass_element_geometry(elem: dict) -> dict | None:
    """Convert an Overpass 'out geom' element into a GeoJSON geometry.

    way -> Polygon, relation -> Polygon/MultiPolygon built from its members.
    """
    etype = elem.get("type")
    if etype == "way":
        ring = _overpass_ring(elem.get("geometry", []))
        if len(ring) < 4:
            return None
        return {"type": "Polygon", "coordinates": [ring]}

    if etype == "relation":
        outers = []
        inners = []
        for m in elem.get("members", []):
            ring = _overpass_ring(m.get("geometry", []))
            if len(ring) < 4:
                continue
            if m.get("role") == "inner":
                inners.append(ring)
            else:
                outers.append(ring)
        if not outers:
            return None
        if len(outers) == 1:
            return {"type": "Polygon", "coordinates": [outers[0]] + inners}
        return {
            "type": "MultiPolygon",
            "coordinates": [[o] + inners for o in outers],
        }
    return None


def _overpass_query(lat: float, lon: float, radius_m: float) -> str:
    radius = max(50, min(int(radius_m), 800))
    return (
        f"[out:json][timeout:20];"
        f"(way[\"building\"](around:{radius},{lat},{lon});"
        f"way[\"landuse\"](around:{radius},{lat},{lon}););"
        f"out geom;"
    )


async def _overpass_request(query: str) -> dict | None:
    """Query all Overpass mirrors in parallel; return the first success.

    Mirrors answering 200 with an empty element list (e.g. regional-only
    instances queried outside their coverage) are only used as a last resort,
    so a transient failure on a full mirror cannot shadow real data."""
    async def _fetch(client: httpx.AsyncClient, url: str):
        try:
            r = await client.get(url, params={"data": query})
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None

    async with httpx.AsyncClient(timeout=_OVERPASS_TIMEOUT, headers=_HEADERS) as client:
        results = await asyncio.gather(
            *[_fetch(client, url) for url in OVERPASS_MIRRORS],
            return_exceptions=True,
        )
    fallback = None
    for res in results:
        if isinstance(res, dict):
            if res.get("elements"):
                return res
            if fallback is None:
                fallback = res
    return fallback


def select_overpass_element(elements: list, lon: float, lat: float) -> tuple[dict, dict] | None:
    """Return the (element, geometry) containing the point, smallest area wins.

    Buildings are preferred over land-use parcels at equal area."""
    candidates = []
    for elem in elements:
        geom = overpass_element_geometry(elem)
        if not geom:
            continue
        if point_in_polygon(lon, lat, geom):
            tags = elem.get("tags", {})
            building = bool(tags.get("building"))
            candidates.append((geojson_area_m2(geom), not building, elem, geom))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2], candidates[0][3]


async def _parcel_overpass(lat: float, lon: float, radius_m: float) -> dict:
    country = detect_country(lat, lon)
    data = await _overpass_request(_overpass_query(lat, lon, radius_m))
    if not data:
        return {
            "country": country,
            "found": False,
            "provider": "OpenStreetMap",
            "message": "Aucune donnée OpenStreetMap disponible à cet emplacement.",
        }

    selected = select_overpass_element(data.get("elements", []), lon, lat)
    if not selected:
        return {
            "country": country,
            "found": False,
            "provider": "OpenStreetMap",
            "message": "Aucun bâtiment ou parcelle OpenStreetMap trouvé à cet emplacement. "
                       "Utilisez le dessin manuel sur la carte.",
        }

    elem, geom = selected
    tags = elem.get("tags", {})
    return {
        "country": country,
        "found": True,
        "provider": "OpenStreetMap",
        "reference": f'{elem.get("type")}/{elem.get("id")}',
        "kind": tags.get("building") or tags.get("landuse"),
        "source_area_m2": None,
        "calculated_area_m2": round(geojson_area_m2(geom), 1),
        "geometry": geom,
    }


async def _parcel_france(lat: float, lon: float, radius_m: float) -> dict:
    dlat = radius_m / 111320.0
    dlon = radius_m / (111320.0 * math.cos(math.radians(lat))) if abs(lat) < 89 else 0.1
    bbox = f"{lon-dlon},{lat-dlat},{lon+dlon},{lat+dlat},epsg:4326"

    # --- Step 1: try to find a building footprint (BDTOPO) ---
    # Use a tight bbox around the point to avoid fetching hundreds of buildings.
    dlat_b = 50.0 / 111320.0
    dlon_b = 50.0 / (111320.0 * math.cos(math.radians(lat))) if abs(lat) < 89 else 0.001
    bbox_building = f"{lon-dlon_b},{lat-dlat_b},{lon+dlon_b},{lat+dlat_b},epsg:4326"
    building_params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": IGN_BUILDING_LAYER,
        "bbox": bbox_building, "srsName": "urn:ogc:def:crs:EPSG::4326",
        "outputFormat": "application/json",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        try:
            r = await client.get(IGN_WFS, params=building_params)
            r.raise_for_status()
            building_data = r.json()
        except Exception:
            building_data = {}

    building_features = building_data.get("features", [])
    building = _feature_containing_point(building_features, lon, lat)
    if building:
        geom = building.get("geometry", {})
        props = building.get("properties", {})
        area = geojson_area_m2(geom)
        if area > 0:
            return {
                "country": "france",
                "found": True,
                "provider": "IGN",
                "reference": props.get("cleabs") or props.get("id"),
                "kind": "building",
                "source_area_m2": None,
                "calculated_area_m2": round(area, 1),
                "geometry": geom,
            }

    # --- Step 2: fallback to cadastral parcel ---
    parcel_params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": "CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle",
        "bbox": bbox, "srsName": "urn:ogc:def:crs:EPSG::4326",
        "outputFormat": "application/json",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        try:
            r = await client.get(IGN_WFS, params=parcel_params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return {"country": "france", "found": False, "provider": "IGN",
                    "message": f"Erreur WFS IGN : {e}"}

    features = data.get("features", [])
    feature = _feature_containing_point(features, lon, lat)
    if not feature:
        return {"country": "france", "found": False, "provider": "IGN",
                "message": "Aucune parcelle cadastrale trouvée à cet emplacement."}

    props = feature.get("properties", {})
    return {
        "country": "france",
        "found": True,
        "provider": "IGN",
        "reference": props.get("id"),
        "kind": "parcel",
        "source_area_m2": props.get("contenance"),
        "calculated_area_m2": round(geojson_area_m2(feature["geometry"]), 1),
        "geometry": feature.get("geometry"),
    }


async def _parcel_netherlands(lat: float, lon: float, radius_m: float) -> dict:
    dlat = radius_m / 111320.0
    dlon = radius_m / (111320.0 * math.cos(math.radians(lat)))
    bbox = f"{lon-dlon},{lat-dlat},{lon+dlon},{lat+dlat}"
    params = {"bbox": bbox, "f": "json"}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        try:
            r = await client.get(PDOK_PARCEL, params=params)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return {"country": "netherlands", "found": False, "provider": "PDOK",
                    "message": f"Erreur PDOK : {e}"}

    features = data.get("features", [])
    feature = _feature_containing_point(features, lon, lat)
    if not feature:
        return {"country": "netherlands", "found": False, "provider": "PDOK",
                "message": "Aucune perceel trouvée à cet emplacement."}

    props = feature.get("properties", {})
    return {
        "country": "netherlands",
        "found": True,
        "provider": "PDOK",
        "reference": props.get("perceelnummer"),
        "source_area_m2": props.get("kadastrale_grootte_waarde"),
        "calculated_area_m2": round(geojson_area_m2(feature["geometry"]), 1),
        "geometry": feature.get("geometry"),
    }
