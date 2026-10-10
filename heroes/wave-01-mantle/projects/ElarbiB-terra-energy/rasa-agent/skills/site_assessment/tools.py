import httpx

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

API_BASE = "http://localhost:8000"
_TIMEOUT = httpx.Timeout(180.0)


async def _analyze_site(latitude: float, longitude: float, start_date: str, end_date: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{API_BASE}/api/analysis/site",
            json={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "resolution": "hourly",
            },
        )
        r.raise_for_status()
        return r.json()


@tool(description=(
    "Analyze the solar energy potential of a location from satellite data (PVGIS, NSRDB, ERA5, Open-Meteo, NASA POWER). "
    "Returns GHI and DNI averages, optimal tilt/azimuth, performance ratio, specific "
    "yield in kWh/kWp/year and a solar score out of 100. Dates use YYYYMMDD format. "
    "Includes weather quality metadata (source, uncertainty, bias correction)."
))
async def get_solar_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    context: ToolContext = None,
) -> ToolResult:
    d = await _analyze_site(latitude, longitude, start_date, end_date)
    weather_quality = d.get("weather_quality", {})
    return ToolResult(llm_response={
        "latitude": latitude,
        "longitude": longitude,
        "period": f"{start_date}-{end_date}",
        "solar_score": d.get("solar_score"),
        "solar_analysis": d.get("solar_data"),
        "weather_quality": weather_quality,
    })


@tool(description=(
    "Analyze the wind energy potential of a location from satellite/reanalysis data. "
    "Returns average wind speed at hub height, Weibull k/c parameters, wind power "
    "density, eligible hours, capacity factor and a wind score out of 100. "
    "Dates use YYYYMMDD format. Includes weather quality metadata."
))
async def get_wind_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    context: ToolContext = None,
) -> ToolResult:
    d = await _analyze_site(latitude, longitude, start_date, end_date)
    weather_quality = d.get("weather_quality", {})
    return ToolResult(llm_response={
        "latitude": latitude,
        "longitude": longitude,
        "period": f"{start_date}-{end_date}",
        "wind_score": d.get("wind_score"),
        "wind_analysis": d.get("wind_data"),
        "weather_quality": weather_quality,
    })


@tool(description=(
    "Get a complete renewable energy assessment for one location: solar score, wind "
    "score, hybrid complementarity, overall score out of 100, dominant resource and a "
    "recommendation. Use this when the user asks generally about a site's potential. "
    "Dates use YYYYMMDD format. Includes weather quality metadata (sources used, uncertainty, bias correction)."
))
async def get_site_score(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    context: ToolContext = None,
) -> ToolResult:
    d = await _analyze_site(latitude, longitude, start_date, end_date)
    weather_quality = d.get("weather_quality", {})
    return ToolResult(llm_response={
        "latitude": latitude,
        "longitude": longitude,
        "period": f"{start_date}-{end_date}",
        "overall_score": d.get("overall_score"),
        "solar_score": d.get("solar_score"),
        "wind_score": d.get("wind_score"),
        "dominant_resource": d.get("dominant_resource"),
        "recommendation": d.get("recommendation"),
        "solar_analysis": d.get("solar_data"),
        "wind_analysis": d.get("wind_data"),
        "hybrid_analysis": d.get("hybrid_data"),
        "weather_quality": weather_quality,
    })


@tool(description=(
    "Fetch raw weather data from multiple sources (PVGIS, NSRDB, ERA5, Open-Meteo, NASA POWER) "
    "with full quality pipeline: cross-validation, bias correction, uncertainty scoring, and fusion. "
    "Returns standardized variables (GHI, DNI, DHI, WS, WD, T2M, RH, PS) with quality metrics. "
    "Use 'strategy' to control source selection: 'geo_priority' (default), 'best_quality', 'cross_validate'. "
    "Dates use YYYYMMDD format."
))
async def get_weather_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: list[str] = None,
    strategy: str = "geo_priority",
    topography: str = "flat",
    context: ToolContext = None,
) -> ToolResult:
    vars_list = variables or ["ALL"]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{API_BASE}/api/weather/fetch",
            json={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "variables": vars_list,
                "resolution": "hourly",
                "use_tmy": False,
                "strategy": strategy,
                "topography": topography,
            },
        )
        r.raise_for_status()
        return ToolResult(llm_response=r.json())


@tool(description=(
    "Compare weather data quality between multiple sources for a location and period. "
    "Returns cross-validation results (correlation, bias %, flags) and fused quality metrics. "
    "Use to explain differences between data sources or validate data reliability. "
    "Dates use YYYYMMDD format."
))
async def compare_weather_sources(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    context: ToolContext = None,
) -> ToolResult:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(
            f"{API_BASE}/api/weather/quality/{latitude}/{longitude}",
            params={"start_date": start_date, "end_date": end_date},
            timeout=60.0,
        )
        r.raise_for_status()
        return ToolResult(llm_response=r.json())


@tool(description=(
    "List all available weather data sources with their capabilities, coverage regions, "
    "priority, and base quality scores. Use to inform the user about data options."
))
async def list_weather_sources(
    context: ToolContext = None,
) -> ToolResult:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{API_BASE}/api/weather/sources")
        r.raise_for_status()
        return ToolResult(llm_response={"sources": r.json()})