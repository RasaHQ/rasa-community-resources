import { SiteScore, ComparisonResult } from '../types';

export function buildAnalysisContext(
  siteResult?: SiteScore | null,
  comparisonResult?: ComparisonResult | null,
): string {
  const parts: string[] = [];
  if (siteResult) {
    const s = siteResult;
    parts.push(`SITE ANALYSE: ${s.latitude.toFixed(4)}, ${s.longitude.toFixed(4)}`);
    parts.push(`Score Global: ${s.overall_score}/100 | Solaire: ${s.solar_score} | Eolien: ${s.wind_score}`);
    parts.push(`Ressource dominante: ${s.dominant_resource || 'N/A'}`);
    parts.push(`Recommandation: ${s.recommendation}`);
    if (s.hybrid_data) {
      parts.push(`\n--- HYBRIDE ---`);
      parts.push(`Complementarite: ${s.hybrid_data.complementarity_score?.toFixed(0) || 'N/A'}/100 | P90 combine: ${((s.hybrid_data.p90_annual_kwh || 0) / 1000).toFixed(0)} MWh`);
    }
    if (s.solar_data) {
      const d = s.solar_data;
      parts.push(`\n--- SOLAIRE ---`);
      parts.push(`GHI: ${d.ghi_avg} kWh/m2/j | DNI: ${d.dni_avg} | DHI: ${d.dhi_avg}`);
      parts.push(`Score: ${d.score}/100 | Classe: ${d.resource_class || 'N/A'}`);
      parts.push(`PR: ${((d.performance_ratio || 0) * 100).toFixed(1)}% | CF: ${(d.capacity_factor * 100).toFixed(1)}%`);
      parts.push(`Yield: ${d.specific_yield_kwh_kwp?.toFixed(0) || 'N/A'} kWh/kWp | P50: ${((d.p50_annual_kwh || 0) / 1000).toFixed(0)} MWh | P90: ${((d.p90_annual_kwh || 0) / 1000).toFixed(0)} MWh`);
    }
    if (s.wind_data) {
      const d = s.wind_data;
      parts.push(`\n--- EOLIEN ---`);
      parts.push(`WS 50m: ${d.ws_50m_avg} m/s | Direction: ${d.dominant_direction}`);
      parts.push(`Score: ${d.score}/100 | WPD: ${d.wind_power_density} W/m2`);
      parts.push(`Weibull: k=${d.weibull_k} c=${d.weibull_c} | TI: ${d.turbulence_intensity}`);
      parts.push(`Yield: ${d.specific_yield_kwh_kw?.toFixed(0) || 'N/A'} kWh/kW | P50: ${((d.p50_annual_kwh || 0) / 1000).toFixed(0)} MWh | P90: ${((d.p90_annual_kwh || 0) / 1000).toFixed(0)} MWh`);
    }
  }
  if (comparisonResult && comparisonResult.sites.length > 0) {
    parts.push(`\n--- COMPARAISON MULTI-SITES ---`);
    parts.push(`Meilleur site: ${comparisonResult.best_site.latitude.toFixed(4)}, ${comparisonResult.best_site.longitude.toFixed(4)} (score ${comparisonResult.best_site.overall_score}/100)`);
    comparisonResult.sites.forEach((s, i) => {
      parts.push(`Site ${i + 1}: ${s.latitude.toFixed(4)}, ${s.longitude.toFixed(4)} | Score: ${s.overall_score} | Solaire: ${s.solar_score} | Eolien: ${s.wind_score}${s.hybrid_data ? ' | Hybride: ' + s.hybrid_data.complementarity_score?.toFixed(0) + '/100' : ''}`);
    });
  }
  return parts.join('\n');
}