"""Weather Provider Registry - Manages provider selection, routing, and fallback."""

import yaml
import asyncio
from typing import Optional
from pathlib import Path

from .weather_provider import WeatherProvider, WeatherRequest, WeatherResponse, WeatherProviderError
from .providers import PROVIDER_CLASSES


class ProviderRegistry:
    """Registry for weather providers with geo-routing and fallback logic."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.providers: dict[str, WeatherProvider] = {}
        self._providers_initialized = False

    def _load_config(self) -> dict:
        """Load configuration from YAML."""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _init_providers(self):
        """Initialize all enabled providers."""
        if self._providers_initialized:
            return
        
        # Ensure env vars are loaded
        from dotenv import load_dotenv
        import os
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
        
        cache_dir = self.config.get("cache", {}).get("directory", "cache/weather")
        
        for source_name, source_config in self.config.get("sources", {}).items():
            if not source_config.get("enabled", True):
                continue
            
            provider_class = PROVIDER_CLASSES.get(source_name)
            if not provider_class:
                continue
            
            try:
                provider = provider_class(
                    name=source_name,
                    config=source_config,
                    cache_dir=cache_dir,
                    timeout=source_config.get("timeout", 30),
                )
                self.providers[source_name] = provider
            except WeatherProviderError as e:
                print(f"Warning: Failed to initialize {source_name}: {e}")
        
        self._providers_initialized = True

    def _ensure_initialized(self):
        """Ensure providers are initialized."""
        if not self._providers_initialized:
            self._init_providers()

    def get_provider(self, name: str) -> Optional[WeatherProvider]:
        """Get provider by name."""
        self._ensure_initialized()
        return self.providers.get(name)

    def get_providers_for_region(self, region: str) -> list[WeatherProvider]:
        """Get providers for a region in priority order."""
        self._ensure_initialized()
        routing = self.config.get("routing", {})
        geo_mapping = routing.get("geo_mapping", {})
        
        provider_names = geo_mapping.get(region, geo_mapping.get("GLOBAL", []))
        providers = []
        
        for name in provider_names:
            if name in self.providers:
                providers.append(self.providers[name])
        
        # Sort by priority
        providers.sort(key=lambda p: self.config["sources"][p.name].get("priority", 99))
        return providers

    def get_region(self, lat: float, lon: float) -> str:
        """Determine region from coordinates."""
        self._ensure_initialized()
        # Use first provider's region detection
        for provider in self.providers.values():
            return provider.get_region(lat, lon)
        return "GLOBAL"

    def select_providers(
        self,
        lat: float,
        lon: float,
        variables: list[str],
        strategy: Optional[str] = None,
    ) -> list[WeatherProvider]:
        """Select providers based on strategy."""
        self._ensure_initialized()
        strategy = strategy or self.config.get("routing", {}).get("default_strategy", "geo_priority")
        region = self.get_region(lat, lon)
        
        if strategy == "geo_priority":
            return self.get_providers_for_region(region)
        
        elif strategy == "best_quality":
            # Get all providers supporting region, sort by quality_base
            all_providers = self.get_providers_for_region(region)
            all_providers.sort(key=lambda p: self.config["sources"][p.name].get("quality_base", 0), reverse=True)
            return all_providers
        
        elif strategy == "cross_validate":
            # Return providers for cross-validation (need at least 2)
            providers = self.get_providers_for_region(region)
            min_sources = self.config.get("routing", {}).get("require_min_sources", 2)
            return providers[:max(min_sources, len(providers))]
        
        return self.get_providers_for_region(region)

    async def fetch_all(
        self,
        request: WeatherRequest,
        providers: Optional[list[WeatherProvider]] = None,
    ) -> list[WeatherResponse]:
        """Fetch from multiple providers in parallel."""
        self._ensure_initialized()
        if providers is None:
            providers = self.select_providers(
                request.latitude,
                request.longitude,
                request.variables,
            )
        
        tasks = [p.fetch(request) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        responses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Provider {providers[i].name} failed: {result}")
            else:
                responses.append(result)
        
        return responses

    def get_config(self, source_name: str) -> dict:
        """Get config for a source."""
        return self.config.get("sources", {}).get(source_name, {})

    def list_providers(self) -> list[dict]:
        """List all providers with their status."""
        self._ensure_initialized()
        result = []
        for name, provider in self.providers.items():
            config = self.config.get("sources", {}).get(name, {})
            result.append({
                "name": name,
                "enabled": config.get("enabled", True),
                "priority": config.get("priority", 99),
                "regions": provider.supported_regions,
                "variables": provider.supported_variables,
                "quality_base": config.get("quality_base", 0.8),
            })
        return result