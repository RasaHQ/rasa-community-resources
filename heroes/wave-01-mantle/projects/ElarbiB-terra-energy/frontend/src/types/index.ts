export interface OrientationScenario {
  label: string;
  tilt_deg: number;
  azimuth_deg: number;
  energy_kwh: number;
}

export interface SolarData {
  ghi_avg: number;
  dni_avg: number;
  dhi_avg: number;
  clear_sky_avg: number;
  peak_sun_hours: number;
  capacity_factor: number;
  annual_energy_kwh: number;
  score: number;
  monthly_ghi?: Record<string, number>;
  monthly_dni?: Record<string, number>;
  monthly_dhi?: Record<string, number>;
  variability?: number;
  poa_irradiance?: number;
  performance_ratio?: number;
  temperature_loss_pct?: number;
  losses_breakdown?: {
    temperature: number;
    inverter: number;
    wiring: number;
    soiling: number;
    mismatch: number;
    shading: number;
    total: number;
  };
  annual_energy_corrected_kwh?: number;
  resource_class?: string;
  t_ambient_avg?: number;
  t_cell_estimated?: number;
  clarity_ratio?: number;
  specific_yield_kwh_kwp?: number;
  p50_annual_kwh?: number;
  p75_annual_kwh?: number;
  p90_annual_kwh?: number;
  capacity_kw?: number;
  poa_annual_kwh_m2?: number;
  days_covered?: number;
  optimized_tilt_deg?: number;
  optimized_azimuth_deg?: number;
  orientation_scenarios?: OrientationScenario[];
}

export interface WindData {
  ws_2m_avg: number;
  ws_50m_avg: number;
  ws_hub_avg?: number;
  wind_power_density: number;
  wind_power_density_corrected?: number;
  dominant_direction: string;
  eligible_hours_pct: number;
  capacity_factor: number;
  annual_energy_kwh: number;
  annual_energy_corrected_kwh?: number;
  score: number;
  wind_rose?: Record<string, number>;
  monthly_ws?: Record<string, number>;
  variability?: number;
  weibull_k?: number;
  weibull_c?: number;
  turbulence_intensity?: number;
  iec_wind_class?: string;
  iec_turbulence_cat?: string;
  nrel_pd_class?: number;
  wind_shear_exponent?: number;
  air_density?: number;
  hub_height_m?: number;
  turbine_rating_kw?: number;
  specific_yield_kwh_kw?: number;
  p50_annual_kwh?: number;
  p75_annual_kwh?: number;
  p90_annual_kwh?: number;
  days_covered?: number;
  wind_speed_histogram?: {
    bins: string[];
    frequencies: number[];
    weibull_pdf: number[];
  };
}

export interface HybridData {
  annual_energy_kwh?: number;
  annual_energy_corrected_kwh?: number;
  p50_annual_kwh?: number;
  p90_annual_kwh?: number;
  p10_power_kw?: number;
  productive_hours_pct?: number;
  solar_share_pct?: number;
  wind_share_pct?: number;
  complementarity_score?: number;
  profile_correlation?: number;
  days_covered?: number;
}

export interface SystemProposal {
  installation_type?: string;
  installation_label?: string;
  occupation_factor?: number;
  available_area_m2?: number;
  usable_area_m2?: number;
  module?: { name: string; power_w: number; area_m2: number; efficiency_pct: number; temperature_coefficient_pct_c: number };
  n_modules?: number;
  proposed_kw?: number;
  inverter?: { name: string; pac_w: number; pdc_w: number; efficiency_pct: number } | null;
  n_inverters?: number;
  warning?: string;
}

export interface WeatherQuality {
  primary_source?: string;
  sources_used?: string[];
  quality?: Record<string, {
    score: number;
    uncertainty_pct: number;
    bias_corrected: boolean;
  }>;
  validation_flags?: string[];
}

export interface SiteScore {
  name?: string;
  latitude: number;
  longitude: number;
  solar_score: number;
  wind_score: number;
  overall_score: number;
  recommendation: string;
  dominant_resource?: string;
  solar_data: SolarData | null;
  wind_data: WindData | null;
  hybrid_data?: HybridData | null;
  system_proposal?: SystemProposal | null;
  weather_quality?: WeatherQuality;
}

export interface ComparisonResult {
  sites: SiteScore[];
  best_site: SiteScore;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
