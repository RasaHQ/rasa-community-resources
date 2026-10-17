"""Weather Quality Engine - Cross-validation, bias correction, uncertainty scoring."""

import numpy as np
import pandas as pd
from typing import Optional
from dataclasses import dataclass

from .weather_provider import WeatherResponse, QualityMetadata


# Physical plausibility bounds for weather variables
PHYSICAL_BOUNDS = {
    "ghi": (0, 1500),       # W/m2 - max solar constant ~1361
    "dni": (0, 1100),       # W/m2 - max direct normal
    "dhi": (0, 800),        # W/m2 - diffuse
    "ws": (0, 35),          # m/s - extreme wind gusts
    "ws50m": (0, 40),       # m/s at 50m
    "wd": (0, 360),         # degrees
    "t2m": (-50, 60),       # °C
    "rh": (0, 100),         # %
    "ps": (80000, 110000),  # Pa
}

# Monthly average bounds (more restrictive for averages)
MONTHLY_AVG_BOUNDS = {
    "ws": (0, 12),          # m/s - monthly avg rarely exceeds 12
    "ws50m": (0, 14),       # m/s at 50m
    "ghi": (0, 500),        # W/m2 monthly avg
    "dni": (0, 400),        # W/m2 monthly avg
}

# Source reliability for wind (higher = more trustworthy)
WIND_SOURCE_RELIABILITY = {
    "era5": 1.0,
    "pvgis": 0.9,
    "nsrdb": 0.9,
    "nasa_power": 0.7,
    "open_meteo": 0.6,      # Known issues with wind in some regions
}


@dataclass
class SanityResult:
    """Result of sanity check for a variable from a source."""
    variable: str
    source: str
    check_type: str  # "RANGE", "MONTHLY_AVG", "OUTLIER"
    passed: bool
    value: float
    expected_range: tuple
    severity: str  # "INFO", "WARNING", "CRITICAL"
    message: str


class SanityChecker:
    """Validate physical plausibility of weather data."""
    
    def __init__(self):
        self.bounds = PHYSICAL_BOUNDS
        self.monthly_bounds = MONTHLY_AVG_BOUNDS
        self.wind_reliability = WIND_SOURCE_RELIABILITY
    
    def check(self, responses: list[WeatherResponse]) -> list[SanityResult]:
        """Run all sanity checks on responses."""
        results = []
        for resp in responses:
            results.extend(self._check_ranges(resp))
            results.extend(self._check_monthly_averages(resp))
            results.extend(self._check_outliers(resp))
        return results
    
    def _check_ranges(self, resp: WeatherResponse) -> list[SanityResult]:
        """Check if values are within physical bounds."""
        results = []
        for var, (min_val, max_val) in self.bounds.items():
            if var not in resp.data.columns:
                continue
            series = resp.data[var].dropna()
            if len(series) == 0:
                continue
            
            violations = series[(series < min_val) | (series > max_val)]
            if len(violations) > 0:
                pct = len(violations) / len(series) * 100
                severity = "CRITICAL" if pct > 5 else "WARNING"
                results.append(SanityResult(
                    variable=var,
                    source=resp.source,
                    check_type="RANGE",
                    passed=False,
                    value=violations.mean(),
                    expected_range=(min_val, max_val),
                    severity=severity,
                    message=f"{pct:.1f}% of {var} values outside physical bounds [{min_val}, {max_val}]",
                ))
            else:
                results.append(SanityResult(
                    variable=var,
                    source=resp.source,
                    check_type="RANGE",
                    passed=True,
                    value=series.mean(),
                    expected_range=(min_val, max_val),
                    severity="INFO",
                    message="All values within physical bounds",
                ))
        return results
    
    def _check_monthly_averages(self, resp: WeatherResponse) -> list[SanityResult]:
        """Check monthly averages against typical climatological ranges."""
        results = []
        for var, (min_val, max_val) in self.monthly_bounds.items():
            if var not in resp.data.columns:
                continue
            series = resp.data[var].dropna()
            if len(series) == 0:
                continue
            
            monthly_avg = series.resample('ME').mean()
            violations = monthly_avg[(monthly_avg < min_val) | (monthly_avg > max_val)]
            if len(violations) > 0:
                pct = len(violations) / len(monthly_avg) * 100
                # For wind, be more strict - monthly avg > 12 m/s is very rare
                if var in ["ws", "ws50m"]:
                    severity = "CRITICAL" if pct > 10 else "WARNING"
                else:
                    severity = "CRITICAL" if pct > 20 else "WARNING"
                results.append(SanityResult(
                    variable=var,
                    source=resp.source,
                    check_type="MONTHLY_AVG",
                    passed=False,
                    value=violations.mean(),
                    expected_range=(min_val, max_val),
                    severity=severity,
                    message=f"{pct:.1f}% of monthly {var} averages outside typical range [{min_val}, {max_val}]",
                ))
        return results
    
    def _check_outliers(self, resp: WeatherResponse) -> list[SanityResult]:
        """Check for statistical outliers using IQR method."""
        results = []
        for var in resp.data.columns:
            if var not in self.bounds:
                continue
            series = resp.data[var].dropna()
            if len(series) < 10:
                continue
            
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 3 * IQR
            upper_bound = Q3 + 3 * IQR
            
            outliers = series[(series < lower_bound) | (series > upper_bound)]
            if len(outliers) > 0:
                pct = len(outliers) / len(series) * 100
                # Only flag if significant portion are outliers
                if pct > 1:
                    severity = "CRITICAL" if pct > 5 else "WARNING"
                    results.append(SanityResult(
                        variable=var,
                        source=resp.source,
                        check_type="OUTLIER",
                        passed=False,
                        value=outliers.mean(),
                        expected_range=(lower_bound, upper_bound),
                        severity=severity,
                        message=f"{pct:.1f}% of {var} values are statistical outliers (3*IQR)",
                    ))
        return results
    
    def get_reliability_score(self, source: str, variable: str) -> float:
        """Get reliability score for a source/variable combination."""
        if variable in ["ws", "ws50m", "wd"]:
            return self.wind_reliability.get(source.lower(), 0.5)
        return 1.0  # Solar variables generally reliable


@dataclass
class ValidationResult:
    """Result of cross-validation between sources."""
    variable: str
    source_a: str
    source_b: str
    correlation: float
    bias_pct: float  # (A - B) / B * 100
    rmse: float
    n_samples: int
    flag: str  # "OK", "WARNING", "CRITICAL"


class CrossValidator:
    """Cross-validate weather data between multiple sources."""


@dataclass
class ValidationResult:
    """Result of cross-validation between sources."""
    variable: str
    source_a: str
    source_b: str
    correlation: float
    bias_pct: float  # (A - B) / B * 100
    rmse: float
    n_samples: int
    flag: str  # "OK", "WARNING", "CRITICAL"


class CrossValidator:
    """Cross-validate weather data between multiple sources."""

    def __init__(self, threshold: float = 0.15, min_overlap_hours: int = 168):
        self.threshold = threshold  # 15% bias threshold
        self.min_overlap_hours = min_overlap_hours

    def validate(
        self,
        responses: list[WeatherResponse],
        variables: Optional[list[str]] = None,
    ) -> list[ValidationResult]:
        """Cross-validate all pairs of responses for given variables."""
        if len(responses) < 2:
            return []

        if variables is None:
            # Get common variables across all responses
            variables = self._get_common_variables(responses)

        results = []
        for i, resp_a in enumerate(responses):
            for resp_b in responses[i+1:]:
                for var in variables:
                    result = self._validate_pair(resp_a, resp_b, var)
                    if result:
                        results.append(result)

        return results

    def _get_common_variables(self, responses: list[WeatherResponse]) -> list[str]:
        """Get variables present in all responses."""
        common = set()
        for resp in responses:
            vars_in_resp = set(resp.data.columns)
            if not common:
                common = vars_in_resp
            else:
                common &= vars_in_resp
        return list(common)

    def _validate_pair(
        self,
        resp_a: WeatherResponse,
        resp_b: WeatherResponse,
        variable: str,
    ) -> Optional[ValidationResult]:
        """Validate a single variable between two responses."""
        if variable not in resp_a.data.columns or variable not in resp_b.data.columns:
            return None

        # Align on time index
        df_a = resp_a.data[variable].dropna()
        df_b = resp_b.data[variable].dropna()

        if len(df_a) == 0 or len(df_b) == 0:
            return None

        # Join on index
        joined = df_a.to_frame("a").join(df_b.to_frame("b"), how="inner").dropna()
        
        if len(joined) < self.min_overlap_hours:
            return None

        a_vals = joined["a"].values
        b_vals = joined["b"].values

        # Calculate metrics
        correlation = np.corrcoef(a_vals, b_vals)[0, 1] if len(a_vals) > 1 else 0
        bias_pct = (np.mean(a_vals) - np.mean(b_vals)) / (np.mean(b_vals) + 1e-10) * 100
        rmse = np.sqrt(np.mean((a_vals - b_vals) ** 2))

        # Determine flag
        if abs(bias_pct) > self.threshold * 100 or correlation < 0.7:
            flag = "CRITICAL"
        elif abs(bias_pct) > self.threshold * 50 or correlation < 0.85:
            flag = "WARNING"
        else:
            flag = "OK"

        return ValidationResult(
            variable=variable,
            source_a=resp_a.source,
            source_b=resp_b.source,
            correlation=round(float(correlation), 4),
            bias_pct=round(float(bias_pct), 2),
            rmse=round(float(rmse), 4),
            n_samples=len(joined),
            flag=flag,
        )

    def get_validation_flags(self, results: list[ValidationResult]) -> list[str]:
        """Extract flags for quality metadata."""
        flags = []
        for r in results:
            if r.flag != "OK":
                flags.append(f"{r.variable}_{r.flag}: {r.source_a}_vs_{r.source_b}_bias={r.bias_pct}%")
        return flags


class BiasCorrector:
    """Apply bias correction based on cross-validation results."""

    # Static bias tables (source -> variable -> bias factor)
    # These would be calibrated from historical validation
    BIAS_TABLE = {
        "nasa_power": {
            "ghi": 1.12,    # NASA tends to overestimate GHI by ~12%
            "dni": 1.15,
            "dhi": 0.95,
            "ws": 0.88,     # NASA tends to underestimate wind speed
        },
        "era5": {
            "ghi": 0.98,
            "dni": 0.95,
            "ws": 1.05,
        },
        "pvgis": {
            "ghi": 1.0,
            "dni": 1.0,
            "ws": 1.0,
        },
        "nsrdb": {
            "ghi": 1.0,
            "dni": 1.0,
            "ws": 1.0,
        },
        "open_meteo": {
            "ghi": 1.02,
            "dni": 1.0,
            "ws": 0.98,
        },
    }

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def correct(
        self,
        response: WeatherResponse,
        validation_results: Optional[list[ValidationResult]] = None,
    ) -> WeatherResponse:
        """Apply bias correction to a response."""
        if not self.enabled:
            return response

        source = response.source.lower()
        if source not in self.BIAS_TABLE:
            return response

        bias_factors = self.BIAS_TABLE[source]
        corrected_df = response.data.copy()
        corrected_quality = response.quality.copy()

        for var, factor in bias_factors.items():
            if var in corrected_df.columns:
                corrected_df[var] = corrected_df[var] * factor
                
                # Update quality metadata
                if var in corrected_quality:
                    qm = corrected_quality[var]
                    qm.bias_corrected = True
                    qm.source_specific["bias_factor"] = factor
                    # Slightly improve score after correction
                    qm.score = min(1.0, qm.score * 1.02)

        return WeatherResponse(
            source=response.source,
            data=corrected_df,
            metadata={**response.metadata, "bias_corrected": True},
            quality=corrected_quality,
            fetched_at=response.fetched_at,
            request=response.request,
        )


class UncertaintyScorer:
    """Calculate uncertainty scores for weather data."""

    def __init__(self):
        # Topography-based uncertainty modifiers
        self.topo_uncertainty = {
            "flat": 1.0,
            "hilly": 1.3,
            "mountainous": 1.8,
            "coastal": 1.2,
            "urban": 1.1,
        }

    def score(
        self,
        response: WeatherResponse,
        validation_results: Optional[list[ValidationResult]] = None,
        topography: str = "flat",
    ) -> dict[str, QualityMetadata]:
        """Calculate uncertainty for each variable."""
        quality = {}
        topo_mult = self.topo_uncertainty.get(topography, 1.0)

        for var in response.data.columns:
            if var not in response.quality:
                continue

            base_qm = response.quality[var]
            
            # Base uncertainty from data quality
            base_uncertainty = base_qm.uncertainty_pct
            
            # Add validation uncertainty
            val_uncertainty = 0
            if validation_results:
                for vr in validation_results:
                    if vr.variable == var:
                        if vr.flag == "CRITICAL":
                            val_uncertainty += 15
                        elif vr.flag == "WARNING":
                            val_uncertainty += 8
                        # Good agreement reduces uncertainty
                        elif vr.flag == "OK" and vr.correlation > 0.9:
                            val_uncertainty -= 3

            # Topography multiplier
            total_uncertainty = (base_uncertainty + max(0, val_uncertainty)) * topo_mult
            
            # Score inversely related to uncertainty
            score = max(0.0, 1.0 - total_uncertainty / 100)

            quality[var] = QualityMetadata(
                score=round(score, 3),
                uncertainty_pct=round(total_uncertainty, 1),
                bias_corrected=base_qm.bias_corrected,
                validation_flags=base_qm.validation_flags + (
                    [f"TOPO_{topography.upper()}"] if topography != "flat" else []
                ),
                source_specific=base_qm.source_specific,
            )

        return quality


class DataFusion:
    """Fuse multiple weather responses into a single best estimate."""

    def __init__(self):
        pass

    def fuse(
        self,
        responses: list[WeatherResponse],
        validation_results: Optional[list[ValidationResult]] = None,
        request_time_range: Optional[tuple[pd.Timestamp, pd.Timestamp]] = None,
    ) -> tuple[pd.DataFrame, dict[str, QualityMetadata], list[str]]:
        """Fuse responses using quality-weighted average.
        
        Handles non-overlapping time ranges by selecting the provider
        that best matches the requested time range.
        """
        if not responses:
            raise ValueError("No responses to fuse")

        if len(responses) == 1:
            return responses[0].data, responses[0].quality, []

        # Get common variables
        common_vars = set(responses[0].data.columns)
        for r in responses[1:]:
            common_vars &= set(r.data.columns)

        fused_data = {}
        fused_quality = {}
        fusion_flags = []

        for var in common_vars:
            # Collect series and weights
            series_list = []
            weights = []
            sources = []

            for resp in responses:
                if var in resp.data.columns and var in resp.quality:
                    s = resp.data[var].dropna()
                    if len(s) > 0:
                        series_list.append(s)
                        weights.append(resp.quality[var].score)
                        sources.append(resp.source)

            if not series_list:
                continue

            # Check time overlap between all series
            time_ranges = [(s.index.min(), s.index.max()) for s in series_list]
            
            # Check which providers overlap with the requested time range
            providers_covering_request = []
            if request_time_range:
                req_start, req_end = request_time_range
                for i, (tmin, tmax) in enumerate(time_ranges):
                    overlap_start = max(tmin, req_start)
                    overlap_end = min(tmax, req_end)
                    if overlap_start <= overlap_end:
                        coverage = (overlap_end - overlap_start).total_seconds() / 3600
                        if coverage > 0:
                            providers_covering_request.append((i, coverage))
            
            # Check if any pair has time overlap
            has_overlap = False
            for i in range(len(time_ranges)):
                for j in range(i+1, len(time_ranges)):
                    tmin1, tmax1 = time_ranges[i]
                    tmin2, tmax2 = time_ranges[j]
                    if tmin1 <= tmax2 and tmin2 <= tmax1:
                        has_overlap = True
                        break
                if has_overlap:
                    break
            
            # If no overlap among providers covering request, or providers covering request
            # don't overlap with each other, select best matching provider
            if request_time_range and providers_covering_request:
                # Sort by coverage (descending)
                providers_covering_request.sort(key=lambda x: x[1], reverse=True)
                best_idx = providers_covering_request[0][0]
                
                # Use only the best matching provider
                fused_data[var] = series_list[best_idx]
                fused_quality[var] = QualityMetadata(
                    score=weights[best_idx],
                    uncertainty_pct=responses[best_idx].quality[var].uncertainty_pct,
                    bias_corrected=responses[best_idx].quality[var].bias_corrected,
                    validation_flags=[f"SELECTED_BEST_MATCH_{sources[best_idx]}"],
                    source_specific={"source": sources[best_idx], "weight": weights[best_idx]},
                )
                fusion_flags.append(f"{var}_NO_OVERLAP_USED_{sources[best_idx]}")
                continue
            
            # If no providers cover request, or we have overlap, do weighted fusion
            # But still prefer providers covering request if available
            if request_time_range and providers_covering_request:
                # Boost weights for providers covering request
                for i, coverage in providers_covering_request:
                    weights[i] *= (1 + coverage / 1000)

        fused_df = pd.DataFrame(fused_data)
        
        if validation_results:
            for vr in validation_results:
                if vr.flag != "OK":
                    fusion_flags.append(f"{vr.variable}_{vr.flag}_between_{vr.source_a}_{vr.source_b}")

        return fused_df, fused_quality, fusion_flags