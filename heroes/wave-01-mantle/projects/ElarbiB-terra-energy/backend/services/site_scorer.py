from services.nasa_frame import dataframe_to_nasa_format
from services.solar_analysis import analyze_solar
from services.wind_analysis import analyze_wind
from services.hybrid_analysis import analyze_hybrid
from services.i18n import (
    get_lang, pick, REC_EXCELLENT, REC_GOOD, REC_MODERATE, REC_LOW,
    REC_DOMINANT, DOMINANT_LABEL, REC_SOLAR, REC_WIND, REC_HYBRID,
)
from services.weather_service import get_weather_service


def compute_site_score(
    lat: float, lon: float,
    solar_result: dict, wind_result: dict,
    hybrid_result: dict | None = None,
    solar_weight: float = 0.5, wind_weight: float = 0.5,
    lang: str = "fr",
) -> dict:
    lang = get_lang(lang)
    solar_score = solar_result.get("score", 0)
    wind_score = wind_result.get("score", 0)

    # Overall score = weighted by the resources' production shares when the
    # hybrid analysis provides them (per reference scoring), otherwise equal weights.
    if hybrid_result and hybrid_result.get("solar_share_pct") is not None:
        solar_weight = hybrid_result["solar_share_pct"] / 100.0
        wind_weight = hybrid_result["wind_share_pct"] / 100.0

    overall = solar_score * solar_weight + wind_score * wind_weight

    # Hybrid complementarity bonus
    if hybrid_result and hybrid_result.get("complementarity_score", 0) >= 40:
        overall = min(100.0, overall + 5.0)

    if solar_score > wind_score + 10:
        dominant = "solar"
    elif wind_score > solar_score + 10:
        dominant = "wind"
    else:
        dominant = "hybrid"

    solar_class = solar_result.get("resource_class", "N/A")
    wind_class = wind_result.get("iec_wind_class", "N/A")

    parts = []
    if overall >= 70:
        parts.append(pick(REC_EXCELLENT, lang).format(score=overall))
    elif overall >= 55:
        parts.append(pick(REC_GOOD, lang).format(score=overall))
    elif overall >= 40:
        parts.append(pick(REC_MODERATE, lang).format(score=overall))
    else:
        parts.append(pick(REC_LOW, lang).format(score=overall))

    parts.append(pick(REC_DOMINANT, lang).format(resource=DOMINANT_LABEL[dominant][lang]))

    if solar_score >= 60:
        parts.append(pick(REC_SOLAR, lang).format(
            cls=solar_class,
            ghi=solar_result.get('ghi_avg', 0),
            sy=solar_result.get('specific_yield_kwh_kwp', 0),
        ))
    if wind_score >= 50:
        parts.append(pick(REC_WIND, lang).format(
            cls=wind_class,
            ws=wind_result.get('ws_hub_avg', 0),
        ))
    if hybrid_result:
        parts.append(pick(REC_HYBRID, lang).format(
            comp=hybrid_result.get('complementarity_score', 0),
            p90=hybrid_result.get('p90_annual_kwh', 0) / 1000,
        ))

    rec = " ".join(parts)

    return {
        "latitude": lat,
        "longitude": lon,
        "solar_score": round(solar_score, 1),
        "wind_score": round(wind_score, 1),
        "overall_score": round(overall, 1),
        "dominant_resource": dominant,
        "recommendation": rec,
        "solar_data": solar_result,
        "wind_data": wind_result,
        "hybrid_data": hybrid_result,
    }


async def full_site_analysis(
    lat: float, lon: float,
    start: str, end: str,
    resolution: str = "hourly",
    solar_config: dict | None = None,
    wind_config: dict | None = None,
    site_context: dict | None = None,
    lang: str = "fr",
) -> dict:
    lang = get_lang(lang)
    solar_config = dict(solar_config or {})
    wind_config = dict(wind_config or {})
    site_context = dict(site_context or {})

    # Optional system sizing from usable surface (report 4.2)
    proposed = {}
    if site_context.get("usable_area_m2") or site_context.get("available_area_m2"):
        try:
            from services.equipment_catalog import propose_system
            area = float(site_context.get("usable_area_m2") or site_context.get("available_area_m2"))
            proposed = propose_system(
                area_m2=area,
                support=site_context.get("installation_type", "roof"),
                module_name=site_context.get("module_name"),
                inverter_name=site_context.get("inverter_name"),
            )
            if proposed.get("proposed_kw") and solar_config.get("capacity_kw") is None:
                solar_config["capacity_kw"] = proposed["proposed_kw"]
        except Exception:
            proposed = {}

    # Fetch weather data using new multi-source WeatherService
    weather_service = get_weather_service()
    weather_response = await weather_service.get_weather(
        latitude=lat,
        longitude=lon,
        start_date=start,
        end_date=end,
        variables=["ALL"],
        resolution=resolution,
        use_tmy=solar_config.get("use_tmy", False),
    )
    
    # Convert to NASA POWER format for existing analysis modules
    nasa_format_data = dataframe_to_nasa_format(weather_response.data)

    solar_result = analyze_solar(
        nasa_format_data, lat, lon,
        capacity_kw=solar_config.get("capacity_kw", 1000.0),
        tilt_deg=solar_config.get("tilt_deg"),
        azimuth_deg=solar_config.get("azimuth_deg"),
        gamma_pmax_pct=solar_config.get("gamma_pmax_pct", -0.35),
        inverter_efficiency=solar_config.get("inverter_efficiency", 0.96),
        dc_ac_ratio=solar_config.get("dc_ac_ratio", 1.2),
        soiling_loss=solar_config.get("soiling_loss", 0.025),
        wiring_loss=solar_config.get("wiring_loss", 0.02),
        mismatch_loss=solar_config.get("mismatch_loss", 0.015),
        shading_loss=solar_config.get("shading_loss", 0.005),
        availability=solar_config.get("availability", 0.99),
        optimize_orientation=bool(solar_config.get("optimize_orientation", True)),
    )

    wind_result = analyze_wind(
        nasa_format_data,
        hub_height_m=wind_config.get("hub_height_m", 100.0),
        turbine_rating_kw=wind_config.get("turbine_rating_kw", 2000.0),
        v_cut_in=wind_config.get("v_cut_in", 3.0),
        v_rated=wind_config.get("v_rated", 12.0),
        v_cut_out=wind_config.get("v_cut_out", 25.0),
        wake_loss=wind_config.get("wake_loss", 0.05),
        electrical_loss=wind_config.get("electrical_loss", 0.03),
        other_loss=wind_config.get("other_loss", 0.02),
        availability=wind_config.get("availability", 0.97),
        wind_shear_exponent=wind_config.get("wind_shear_exponent"),
    )

    hybrid_result = analyze_hybrid(
        nasa_format_data, lat, lon,
        solar_config=solar_config,
        wind_config=wind_config,
    )

    site = compute_site_score(
        lat, lon,
        solar_result, wind_result,
        hybrid_result=hybrid_result,
        lang=lang,
    )

    # Add weather quality metadata to response
    site["weather_quality"] = {
        "primary_source": weather_response.source,
        "sources_used": weather_response.metadata.get("sources_used", []),
        "quality": {
            k: {
                "score": v.score,
                "uncertainty_pct": v.uncertainty_pct,
                "bias_corrected": v.bias_corrected,
            }
            for k, v in weather_response.quality.items()
        },
        "validation_flags": weather_response.metadata.get("fusion_flags", []),
    }

    if proposed:
        site["system_proposal"] = proposed

    return site


async def compare_sites(sites: list[dict], lang: str = "fr") -> dict:
    lang = get_lang(lang)
    results = []
    for site in sites:
        result = await full_site_analysis(
            site["latitude"], site["longitude"],
            site["start_date"], site["end_date"],
            site.get("resolution", "hourly"),
            solar_config=site.get("solar_config"),
            wind_config=site.get("wind_config"),
            site_context=site.get("site_context"),
            lang=site.get("lang") or lang,
        )
        results.append(result)

    best = max(results, key=lambda x: x["overall_score"])

    return {
        "sites": results,
        "best_site": best,
    }