# Weather Data Sources — Reference Knowledge for Terra

## Overview

TerraEnergy uses a multi-source weather data pipeline that automatically selects the best available data source for a given location and time period. All sources are free and open.

## Available Sources

### 1. PVGIS (Photovoltaic Geographical Information System)
- **Provider**: European Commission Joint Research Centre (JRC)
- **Coverage**: Europe, Africa, Latin America, Asia
- **Resolution**: 5km (SARAH2), 30km (ERA5 via PVGIS)
- **Variables**: GHI, DNI, DHI, Wind speed/direction, Temperature, Humidity, Pressure
- **Time range**: 2005-2020 (SARAH2), 1979-present (ERA5)
- **TMY**: Yes (PVGIS-TMY)
- **Quality base**: 0.95/1.0
- **API**: Free, no key required
- **Best for**: Europe, Africa, project screening, bankable studies

### 2. NSRDB (National Solar Radiation Database)
- **Provider**: NREL (US Department of Energy)
- **Coverage**: Americas (v2+ global)
- **Resolution**: 4km, 30-minute
- **Variables**: GHI, DNI, DHI, Wind speed/direction, Temperature, Humidity, Pressure
- **Time range**: 1998-present
- **TMY**: Yes (PSM3-TMY)
- **Quality base**: 0.93/1.0
- **API**: Free key required (developer.nrel.gov)
- **Best for**: Americas, high-resolution solar studies

### 3. ERA5 (ECMWF Reanalysis v5)
- **Provider**: Copernicus Climate Change Service (C3S)
- **Coverage**: Global
- **Resolution**: 0.25° (~30km), ERA5-Land 0.1° (~9km)
- **Variables**: All (solar, wind, temperature, humidity, pressure, U/V components, etc.)
- **Time range**: 1940-present
- **Quality base**: 0.88/1.0
- **API**: Free key required (cds.climate.copernicus.eu), batch processing
- **Best for**: Global wind studies, long time series, research

### 4. Open-Meteo
- **Provider**: Open-Meteo.com
- **Coverage**: Global
- **Resolution**: Variable (aggregates multiple models)
- **Variables**: GHI, DNI, Wind speed/direction, Temperature, Humidity, Pressure
- **Time range**: 1940-present (historical), forecasts
- **Quality base**: 0.75/1.0
- **API**: Free, no key required, 10k req/day
- **Best for**: Recent data, real-time, quick lookups

### 5. NASA POWER
- **Provider**: NASA Langley Research Center
- **Coverage**: Global
- **Resolution**: 0.5° (~50km)
- **Variables**: All (solar, wind, meteorological)
- **Time range**: 1983-present
- **Quality base**: 0.70/1.0
- **API**: Free, no key required
- **Best for**: Fallback only, coarse global coverage

## Quality Pipeline

### Cross-Validation
When multiple sources cover the same location/period, Terra automatically:
1. Aligns time series on common timestamps
2. Computes Pearson correlation between sources
3. Calculates bias percentage: (Source A - Source B) / Source B × 100
4. Flags discrepancies:
   - **OK**: Correlation ≥ 0.85, bias < 7.5%
   - **WARNING**: Correlation 0.7-0.85 or bias 7.5-15%
   - **CRITICAL**: Correlation < 0.7 or bias > 15%

### Bias Correction
Static bias factors applied per source (calibrated from literature):
- **NASA POWER**: GHI +12%, DNI +15%, DHI -5%, Wind speed -12%
- **ERA5**: GHI -2%, DNI -5%, Wind speed +5%
- **PVGIS**: No correction (reference)
- **NSRDB**: No correction (reference)
- **Open-Meteo**: GHI +2%, Wind speed -2%

### Uncertainty Scoring
Final quality score (0-1) considers:
- Base source quality
- Data completeness
- Cross-validation agreement
- Topography complexity (mountainous ×1.8, coastal ×1.2, urban ×1.1)

### Data Fusion
Quality-weighted average of aligned sources. For non-overlapping time ranges, selects the source best matching the requested period.

## Source Selection Strategy

| Strategy | Behavior |
|----------|----------|
| `geo_priority` (default) | Routes by region: EU/AF/LATAM/ASIA → PVGIS, NA → NSRDB, Global → ERA5 |
| `best_quality` | Sorts all available sources by quality_base descending |
| `cross_validate` | Uses ≥2 sources for validation, requires minimum overlap |

## Interpreting Quality Metadata

When Terra returns weather quality info, it includes:

- **primary_source**: The source with highest weighted quality
- **sources_used**: List of all sources that contributed
- **quality[variable].score**: 0-1 quality score (1 = excellent)
- **quality[variable].uncertainty_pct**: Estimated uncertainty percentage
- **quality[variable].bias_corrected**: Whether static bias correction was applied
- **validation_flags**: Cross-validation warnings (e.g., "GHI_WARNING_between_pvgis_open_meteo")
- **fusion_flags**: Notes on fusion method (e.g., "ghi_NO_OVERLAP_USED_open_meteo")

## Best Practices for Users

1. **For Europe/Africa**: PVGIS is primary, highest quality
2. **For Americas**: NSRDB preferred when available
3. **For wind globally**: ERA5 is best (but batch delay)
4. **For recent data**: Open-Meteo excels
5. **Always check weather_quality** in responses for uncertainty context
6. **Use compare_weather_sources** when users question data reliability

## Limitations

- **Mountainous terrain**: All sources have higher uncertainty (topography multiplier)
- **Coastal areas**: Microclimates not resolved at coarse resolutions
- **Before 2005**: Only ERA5 and NASA POWER available
- **NSRDB/ERA5**: Require API keys, subject to rate limits
- **TMY vs Historical**: TMY = typical year (P50), Historical = actual year