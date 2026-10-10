import httpx

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

API_BASE = "http://localhost:8000"
_TIMEOUT = httpx.Timeout(300.0)


@tool(description=(
    "Compare the renewable energy potential of 2 to 5 locations. Each site needs "
    "latitude, longitude, start_date and end_date (YYYYMMDD). Returns per-site overall, "
    "solar and wind scores plus a ranking identifying the best site. "
    "Includes weather quality metadata for each site (sources used, uncertainty, bias correction)."
))
async def compare_locations(
    sites: list[dict],
    context: ToolContext = None,
) -> ToolResult:
    cleaned = []
    for s in sites[:5]:
        cleaned.append({
            "latitude": float(s["latitude"]),
            "longitude": float(s["longitude"]),
            "start_date": str(s["start_date"]),
            "end_date": str(s["end_date"]),
            "resolution": "hourly",
        })
    if len(cleaned) < 2:
        return ToolResult(llm_response={
            "error": "At least 2 sites are required for a comparison."
        })
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{API_BASE}/api/analysis/compare",
            json={"sites": cleaned},
        )
        r.raise_for_status()
        d = r.json()
    return ToolResult(llm_response={"comparison": d})


@tool(description=(
    "Compare weather data quality across multiple sites. For each site, returns the sources used, "
    "quality scores, uncertainty, and bias correction status. Useful for understanding "
    "data reliability differences between sites in a comparison."
))
async def compare_sites_weather_quality(
    sites: list[dict],
    context: ToolContext = None,
) -> ToolResult:
    cleaned = []
    for s in sites[:5]:
        cleaned.append({
            "latitude": float(s["latitude"]),
            "longitude": float(s["longitude"]),
            "start_date": str(s["start_date"]),
            "end_date": str(s["end_date"]),
        })
    if len(cleaned) < 2:
        return ToolResult(llm_response={
            "error": "At least 2 sites are required."
        })
    
    results = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for site in cleaned:
            try:
                r = await client.get(
                    f"{API_BASE}/api/weather/quality/{site['latitude']}/{site['longitude']}",
                    params={"start_date": site["start_date"], "end_date": site["end_date"]},
                )
                r.raise_for_status()
                results.append({
                    "site": f"{site['latitude']:.4f}, {site['longitude']:.4f}",
                    "weather_quality": r.json(),
                })
            except Exception as e:
                results.append({
                    "site": f"{site['latitude']:.4f}, {site['longitude']:.4f}",
                    "error": str(e),
                })
    
    return ToolResult(llm_response={"sites_weather_quality": results})