"""Keyless map-tile proxy with deterministic error-tile fallback.

Third-party tile hosts (Esri, OpenTopoMap, ...) occasionally answer with
HTTP 200 *error images* ("Map data not available", "API key required")
instead of real tiles. The browser cannot detect those via the standard
`tileerror` event. This module proxies every tile request, detects the
known error payloads by exact byte size, and transparently falls back to
a reliable keyless provider (OSM standard).
"""

import httpx

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
REFERER = "http://localhost:5173/"

OSM = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
ESRI_IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_TOPO = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
OPENTOPO = "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"

# `error_size` is the exact byte length of the provider's error image
# (deterministic detection); None means "never rejected on size".
# @terragrid @map-proxy
PROVIDERS = {
    "satellite": {"url": ESRI_IMAGERY, "error_size": 2521, "subdomains": "", "fallback": "carte"},
    "terrain": {"url": ESRI_TOPO, "error_size": 2521, "subdomains": "", "fallback": "carte"},
    "relief": {"url": OPENTOPO, "error_size": 4343, "subdomains": "abc", "fallback": "carte"},
    "carte": {"url": OSM, "error_size": None, "subdomains": "abc", "fallback": "carte"},
}

_CACHE: dict[str, tuple[bytes, str, str]] = {}
_CACHE_MAX = 4096


def _resolve(template: str, z: int, x: int, y: int, subdomains: str) -> str:
    s = ""
    if "{s}" in template:
        pool = subdomains or "abc"
        s = pool[(x + y + z) % len(pool)]
    return (
        template.replace("{s}", s)
        .replace("{z}", str(z))
        .replace("{x}", str(x))
        .replace("{y}", str(y))
    )


def _chain(provider: str) -> list[str]:
    seen: set[str] = set()
    chain: list[str] = []
    cur = provider
    while cur not in seen:
        seen.add(cur)
        chain.append(cur)
        nxt = PROVIDERS[cur]["fallback"]
        if nxt == cur:
            break
        cur = nxt
    return chain


async def _fetch(url: str) -> tuple[int, str, bytes]:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        r = await client.get(url, headers={"User-Agent": BROWSER_UA, "Referer": REFERER})
        return r.status_code, r.headers.get("content-type", ""), r.content


def _is_good(provider: str, status: int, content_type: str, body: bytes) -> bool:
    if status != 200 or not content_type.lower().startswith("image/") or not body:
        return False
    err = PROVIDERS[provider]["error_size"]
    return err is None or len(body) != err


async def get_tile(provider: str, z: int, x: int, y: int) -> tuple[bytes, str, str]:
    """Return (payload, content_type, source_provider) for one tile.

    Raises KeyError for unknown providers and RuntimeError when no provider
    in the fallback chain produced a usable image.
    """
    if provider not in PROVIDERS:
        raise KeyError(provider)
    key = f"{provider}/{z}/{x}/{y}"
    hit = _CACHE.get(key)
    if hit is not None:
        return hit

    last: tuple[bytes, str] = (b"", "")
    for name in _chain(provider):
        cfg = PROVIDERS[name]
        url = _resolve(cfg["url"], z, x, y, cfg["subdomains"])
        try:
            status, ctype, body = await _fetch(url)
        except httpx.HTTPError:
            status, ctype, body = 0, "", b""
        last = (body, ctype)
        if _is_good(name, status, ctype, body):
            result = (body, ctype, name)
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[key] = result
            return result

    raise RuntimeError("no tile provider available")