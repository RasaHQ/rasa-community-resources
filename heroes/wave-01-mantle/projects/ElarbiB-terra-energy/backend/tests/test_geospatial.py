"""Phase 9 tests — geospatial utilities (report section 3.4)."""

import math

from services.geospatial import (
    geojson_area_m2,
    point_in_polygon,
    detect_country,
    overpass_element_geometry,
    select_overpass_element,
    geocode_fallback_queries,
)

R = 6378137.0


def _square(lon0, lat0, dlon_deg, dlat_deg):
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon0, lat0], [lon0 + dlon_deg, lat0],
            [lon0 + dlon_deg, lat0 + dlat_deg], [lon0, lat0 + dlat_deg],
            [lon0, lat0],
        ]],
    }


def test_geodesic_area_equator_square():
    """1 deg x 1 deg square at equator ~ R^2 * d_lambda * sin(d_phi)."""
    d = 1.0
    a = geojson_area_m2(_square(0.0, 0.0, d, d))
    expected = R ** 2 * math.radians(d) * math.sin(math.radians(d))
    assert abs(a - expected) / expected < 0.001


def test_geodesic_area_scale_with_cos_latitude():
    """Area decreases with cos(lat); a 0.5 deg square near Paris ~ 0.5*0.5*(111km)^2*cos(lat)."""
    lat = 48.8
    d = 0.5
    a = geojson_area_m2(_square(2.3, lat, d, d))
    m_per_deg = 111_320.0
    expected = (d * m_per_deg) ** 2 * math.cos(math.radians(lat))
    assert 0.7 < a / expected < 1.3


def test_point_in_polygon_inside_outside():
    poly = _square(2.0, 48.0, 1.0, 1.0)
    assert point_in_polygon(2.5, 48.5, poly)
    assert not point_in_polygon(5.0, 48.5, poly)


def test_point_in_polygon_multipolygon_and_z():
    geom = {
        "type": "MultiPolygon",
        "coordinates": [[
            [[2.0, 48.0, 100.0], [3.0, 48.0, 100.0],
             [3.0, 49.0, 100.0], [2.0, 49.0, 100.0], [2.0, 48.0, 100.0]],
        ]],
    }
    assert point_in_polygon(2.5, 48.5, geom)
    assert not point_in_polygon(1.0, 48.5, geom)


def test_detect_country_boxes():
    assert detect_country(48.8, 2.3) == "france"
    assert detect_country(52.3, 4.9) == "netherlands"
    assert detect_country(33.5, -7.6) == "morocco"
    assert detect_country(60.0, 10.0) == "other"


def test_geojson_area_empty():
    assert geojson_area_m2({}) == 0.0
    assert geojson_area_m2({"type": "Point", "coordinates": [1.0, 2.0]}) == 0.0


def _op_way(way_id, lon0, lat0, dlon, dlat, **tags):
    nodes = [
        {"lat": lat0, "lon": lon0},
        {"lat": lat0, "lon": lon0 + dlon},
        {"lat": lat0 + dlat, "lon": lon0 + dlon},
        {"lat": lat0 + dlat, "lon": lon0},
    ]
    return {"type": "way", "id": way_id, "tags": tags, "geometry": nodes}


def test_overpass_way_to_polygon():
    geom = overpass_element_geometry(_op_way(1, -7.6, 33.57, 0.002, 0.001, building="yes"))
    assert geom is not None
    assert geom["type"] == "Polygon"
    ring = geom["coordinates"][0]
    assert ring[0] == ring[-1]
    assert ring[0] == [-7.6, 33.57]
    assert geojson_area_m2(geom) > 0


def test_overpass_relation_to_multipolygon():
    outer1 = [
        {"lat": 33.0, "lon": -7.0}, {"lat": 33.0, "lon": -6.99},
        {"lat": 33.01, "lon": -6.99}, {"lat": 33.01, "lon": -7.0},
    ]
    outer2 = [
        {"lat": 33.02, "lon": -7.0}, {"lat": 33.02, "lon": -6.99},
        {"lat": 33.03, "lon": -6.99}, {"lat": 33.03, "lon": -7.0},
    ]
    elem = {
        "type": "relation",
        "id": 42,
        "tags": {"landuse": "residential"},
        "members": [
            {"role": "outer", "geometry": outer1},
            {"role": "outer", "geometry": outer2},
        ],
    }
    geom = overpass_element_geometry(elem)
    assert geom["type"] == "MultiPolygon"
    assert len(geom["coordinates"]) == 2


def test_overpass_degenerate_way_rejected():
    assert overpass_element_geometry({"type": "way", "geometry": []}) is None
    assert overpass_element_geometry({"type": "node", "id": 1}) is None


def test_select_overpass_element_inside():
    elements = [
        _op_way(10, -7.6, 33.57, 0.004, 0.003, building="yes"),
        _op_way(11, -7.599, 33.571, 0.001, 0.001, building="yes"),
    ]
    # point inside both, smallest (11) must win
    sel = select_overpass_element(elements, -7.5985, 33.5715)
    assert sel is not None
    elem, _ = sel
    assert elem["id"] == 11


def test_select_overpass_element_outside():
    assert select_overpass_element([_op_way(10, -7.6, 33.57, 0.001, 0.001)], -7.0, 33.0) is None


def test_overpass_request_prefers_non_empty_mirror(monkeypatch):
    """A regional mirror answering 200 with zero elements must not shadow
    a full mirror that returned real data (regression: osm.ch outside CH)."""
    import asyncio
    from services import geospatial

    responses = {
        "https://mirror-a/api/interpreter": {"elements": []},
        "https://mirror-b/api/interpreter": None,
        "https://mirror-c/api/interpreter": {"elements": [{"type": "way", "id": 1}]},
        "https://mirror-d/api/interpreter": {"elements": []},
    }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            class R:
                status_code = 200

                def json(self):
                    return responses[url]

            return R()

    monkeypatch.setattr(geospatial.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        geospatial, "OVERPASS_MIRRORS", list(responses.keys())
    )
    data = asyncio.run(geospatial._overpass_request("q"))
    assert data is not None
    assert data["elements"], "empty mirror response must not win when data exists"


def test_overpass_request_all_empty_returns_empty_dict(monkeypatch):
    """When every mirror answers empty (genuinely no data), the empty dict is
    still returned so callers can distinguish 'no parcel' from 'no service'."""
    import asyncio
    from services import geospatial

    mirrors = ["https://m1/api/interpreter", "https://m2/api/interpreter"]

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            class R:
                status_code = 200

                def json(self):
                    return {"elements": [], "remark": ""}

            return R()

    monkeypatch.setattr(geospatial.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(geospatial, "OVERPASS_MIRRORS", mirrors)
    data = asyncio.run(geospatial._overpass_request("q"))
    assert data == {"elements": [], "remark": ""}


def test_geocode_fallback_progression():
    qs = geocode_fallback_queries("26 RUE 60 QU ANAS SAFI MAROC")
    assert qs[0] == "26 RUE 60 QU ANAS SAFI MAROC"
    # house number stripped, numbers stripped, QU expanded, streetless
    assert "RUE 60 QU ANAS SAFI MAROC" in qs
    assert "RUE QU ANAS SAFI MAROC" in qs
    assert "26 RUE 60 Quartier ANAS SAFI MAROC" in qs
    assert "Quartier ANAS SAFI MAROC" in qs
    assert "ANAS SAFI MAROC" in qs
    # no duplicates, no empty strings
    assert len(qs) == len(set(qs))
    assert all(q.strip() for q in qs)


def test_geocode_fallback_no_house_number():
    qs = geocode_fallback_queries("Rue de Paris, Lyon")
    assert "Rue de Paris, Lyon" in qs
    assert "de Paris, Lyon" in qs
