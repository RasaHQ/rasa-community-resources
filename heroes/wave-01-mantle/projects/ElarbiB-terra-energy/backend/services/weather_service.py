"""Weather Service Facade - Main entry point for weather data."""

import asyncio
from typing import Optional
from pathlib import Path

import pandas as pd

from .weather_provider import WeatherRequest, WeatherResponse, WeatherProviderError
from .weather_registry import ProviderRegistry
from .weather_quality import (
    CrossValidator, BiasCorrector, UncertaintyScorer, DataFusion,
    SanityChecker, SanityResult, PHYSICAL_BOUNDS
)
from .providers import PROVIDER_CLASSES


class WeatherService:
    """Main weather data service orchestrating all providers and quality checks."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "weather_sources.yaml"
        
        self.registry = ProviderRegistry(str(config_path))
        self.cross_validator = CrossValidator(
            threshold=self.registry.config.get("quality", {}).get("cross_validate_threshold", 0.15),
            min_overlap_hours=self.registry.config.get("quality", {}).get("min_overlap_hours", 168),
        )
        self.bias_corrector = BiasCorrector(
            enabled=self.registry.config.get("quality", {}).get("bias_correction_enabled", True),
        )
        self.uncertainty_scorer = UncertaintyScorer()
        self.data_fusion = DataFusion()
        self.sanity_checker = SanityChecker()

    async def get_weather(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        variables: Optional[list[str]] = None,
        resolution: str = "hourly",
        use_tmy: bool = False,
        strategy: Optional[str] = None,
        topography: str = "flat",
    ) -> WeatherResponse:
        """Get weather data with full quality pipeline."""
        
        request = WeatherRequest(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            variables=variables or ["ALL"],
            resolution=resolution,
            use_tmy=use_tmy,
        )

        # Select providers
        providers = self.registry.select_providers(
            latitude, longitude, request.variables, strategy
        )

        if not providers:
            raise WeatherProviderError(f"No providers available for location ({latitude}, {longitude})")

        # Fetch from all selected providers
        responses = await self.registry.fetch_all(request, providers)

        if not responses:
            raise WeatherProviderError("All providers failed to return data")

        # Sanity checks - filter out sources with critical physical implausibility
        sanity_results = self.sanity_checker.check(responses)
        critical_failures = [r for r in sanity_results if r.severity == "CRITICAL" and not r.passed]
        
        # Track sources with critical failures
        critical_sources = set(r.source for r in critical_failures)
        
        # Filter responses: keep sources without critical failures, or if all fail, keep the best
        filtered_responses = [r for r in responses if r.source not in critical_sources]
        if not filtered_responses:
            # All sources have critical failures - keep the one with highest reliability
            responses.sort(key=lambda r: self.sanity_checker.get_reliability_score(r.source, "ws"), reverse=True)
            filtered_responses = [responses[0]]
        
        responses = filtered_responses

        # Cross-validation
        validation_results = []
        if self.registry.config.get("quality", {}).get("cross_validation_enabled", True):
            validation_results = self.cross_validator.validate(responses, request.variables)

        # Bias correction
        corrected_responses = []
        for resp in responses:
            corrected = self.bias_corrector.correct(resp, validation_results)
            corrected_responses.append(corrected)

        # Recalculate quality with validation results
        for resp in corrected_responses:
            new_quality = self.uncertainty_scorer.score(
                resp, validation_results, topography
            )
            resp.quality = new_quality

        # Apply sanity-based quality penalties
        for resp in corrected_responses:
            source_sanity = [r for r in sanity_results if r.source == resp.source]
            for check in source_sanity:
                if not check.passed and check.severity == "WARNING":
                    # Penalize quality for warnings
                    for var, qm in resp.quality.items():
                        if var == check.variable:
                            qm.score = max(0.1, qm.score * 0.85)
                            qm.uncertainty_pct = min(100, qm.uncertainty_pct * 1.2)

        # Fusion - pass request time range for better provider selection
        request_time_range = (
            pd.Timestamp(request.start_date),
            pd.Timestamp(request.end_date) + pd.Timedelta(hours=23),
        )
        fused_data, fused_quality, fusion_flags = self.data_fusion.fuse(
            corrected_responses, validation_results, request_time_range
        )

        # Determine primary source (highest quality)
        primary_source = max(responses, key=lambda r: sum(q.score for q in r.quality.values()) / max(1, len(r.quality))).source
        sources_used = [r.source for r in responses]

        # Build final response
        final_response = WeatherResponse(
            source=primary_source,
            data=fused_data,
            metadata={
                "sources_used": sources_used,
                "fusion_method": "quality_weighted",
                "validation_results": [
                    {
                        "variable": vr.variable,
                        "source_a": vr.source_a,
                        "source_b": vr.source_b,
                        "correlation": vr.correlation,
                        "bias_pct": vr.bias_pct,
                        "flag": vr.flag,
                    }
                    for vr in validation_results
                ],
                "fusion_flags": fusion_flags,
                "topography": topography,
                "sanity_results": [
                    {
                        "variable": r.variable,
                        "source": r.source,
                        "check_type": r.check_type,
                        "passed": r.passed,
                        "severity": r.severity,
                        "message": r.message,
                    }
                    for r in sanity_results
                ],
            },
            quality=fused_quality,
            request=request,
        )

        return final_response

    async def get_weather_simple(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        variables: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Simple interface returning just the DataFrame."""
        response = await self.get_weather(latitude, longitude, start_date, end_date, variables)
        return response.data

    def get_available_sources(self) -> list[dict]:
        """Get list of available sources."""
        return self.registry.list_providers()

    def get_source_info(self, source_name: str) -> dict:
        """Get detailed info for a source."""
        return self.registry.get_config(source_name)


# Global instance (lazy initialization)
_weather_service: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """Get or create global weather service instance."""
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service


async def fetch_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: Optional[list[str]] = None,
    resolution: str = "hourly",
    use_tmy: bool = False,
    strategy: Optional[str] = None,
) -> WeatherResponse:
    """Convenience function for fetching weather."""
    service = get_weather_service()
    return await service.get_weather(
        latitude, longitude, start_date, end_date,
        variables, resolution, use_tmy, strategy
    )