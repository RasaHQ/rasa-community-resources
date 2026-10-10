import axios from 'axios';

export const api = axios.create({
  baseURL: '/api',
  timeout: 180000,
});

function getLang(): string {
  try {
    return localStorage.getItem('terraenergy.lang') || 'fr';
  } catch {
    return 'fr';
  }
}

api.interceptors.request.use(config => {
  const lang = getLang();
  if (config.data && typeof config.data === 'object' && !Array.isArray(config.data)) {
    config.data.lang = lang;
  }
  config.params = { ...(config.params || {}), lang };
  return config;
});

export interface SiteContext {
  country?: string;
  installation_type?: string;
  available_area_m2?: number;
  usable_area_m2?: number;
  parcel_reference?: string;
  module_name?: string;
  inverter_name?: string;
}

export async function analyzeSite(
  latitude: number,
  longitude: number,
  start: string,
  end: string,
  config: { solar_config?: Record<string, unknown>; wind_config?: Record<string, unknown>; site_context?: SiteContext } = {},
) {
  const res = await api.post('/analysis/site', {
    latitude,
    longitude,
    start_date: start,
    end_date: end,
    resolution: 'hourly',
    solar_config: config.solar_config || {},
    wind_config: config.wind_config || {},
    site_context: config.site_context || {},
  });
  return res.data;
}

export interface CompareSite {
  latitude: number;
  longitude: number;
  start_date: string;
  end_date: string;
  solar_config?: Record<string, unknown>;
  wind_config?: Record<string, unknown>;
  site_context?: SiteContext;
}

export async function compareSites(sites: CompareSite[]) {
  const res = await api.post('/analysis/compare', {
    sites: sites.map(s => ({ ...s, resolution: 'hourly' })),
  });
  return res.data;
}

function getSenderId(): string {
  let id = localStorage.getItem('terraenergy_sender_id');
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem('terraenergy_sender_id', id);
  }
  return id;
}

export async function sendChat(message: string, history: { role: string; content: string }[] = [], context: string = '') {
  const res = await api.post('/llm/chat', {
    message,
    history,
    context,
    sender_id: getSenderId(),
  });
  return res.data.response;
}

export async function geocodeAddress(query: string, country?: string) {
  const res = await api.post('/geospatial/geocode', { query, country });
  return res.data;
}

export async function getParcel(latitude: number, longitude: number, radius_m = 200) {
  const res = await api.post('/geospatial/parcel', { latitude, longitude, radius_m });
  return res.data;
}

export async function getInstallationTypes() {
  const res = await api.get('/geospatial/installation-types');
  return res.data;
}

export async function proposeEquipment(area_m2: number, support: string, module_name?: string, inverter_name?: string) {
  const res = await api.post('/equipment/propose', {
    area_m2,
    support,
    module_name,
    inverter_name,
  });
  return res.data;
}

// Weather API
export interface WeatherSource {
  name: string;
  enabled: boolean;
  priority: number;
  regions: string[];
  variables: string[];
  quality_base: number;
}

export async function getWeatherSources(): Promise<WeatherSource[]> {
  const res = await api.get('/weather/sources');
  return res.data;
}

export async function getWeatherSourceInfo(sourceName: string) {
  const res = await api.get(`/weather/sources/${sourceName}`);
  return res.data;
}

export interface WeatherFetchRequest {
  latitude: number;
  longitude: number;
  start_date: string;
  end_date: string;
  variables?: string[];
  resolution?: string;
  use_tmy?: boolean;
  strategy?: string;
  topography?: string;
}

export interface WeatherQuality {
  score: number;
  uncertainty_pct: number;
  bias_corrected: boolean;
  validation_flags: string[];
}

export interface WeatherFetchResponse {
  source: string;
  data: string; // JSON stringified DataFrame
  metadata: {
    sources_used: string[];
    fusion_method: string;
    validation_results: Array<{
      variable: string;
      source_a: string;
      source_b: string;
      correlation: number;
      bias_pct: number;
      flag: string;
    }>;
    fusion_flags: string[];
    topography: string;
  };
  quality: Record<string, WeatherQuality>;
  fetched_at: string;
}

export async function fetchWeather(request: WeatherFetchRequest): Promise<WeatherFetchResponse> {
  const res = await api.post('/weather/fetch', request);
  return res.data;
}

export interface WeatherQualityResponse {
  location: { latitude: number; longitude: number };
  period: string;
  primary_source: string;
  sources_used: string[];
  validation_results: Array<{
    variable: string;
    source_a: string;
    source_b: string;
    correlation: number;
    bias_pct: number;
    flag: string;
  }>;
  fusion_flags: string[];
  quality: Record<string, WeatherQuality>;
}

export async function getWeatherQuality(
  latitude: number,
  longitude: number,
  startDate: string,
  endDate: string
): Promise<WeatherQualityResponse> {
  const res = await api.get(`/weather/quality/${latitude}/${longitude}`, {
    params: { start_date: startDate, end_date: endDate },
  });
  return res.data;
}
