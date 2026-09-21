/**
 * Shared design tokens for the satellite-instrument UI ("Space Grotesk /
 * JetBrains Mono" look). Import `S` where a component needs the palette.
 */
export const S = {
  bg: '#0a0e17',
  surface: '#111827',
  card: '#1a2236',
  border: 'rgba(255,255,255,0.07)',
  border2: 'rgba(255,255,255,0.12)',
  text: '#e2e8f0',
  text2: '#94a3b8',
  text3: '#64748b',
  solar: '#f5a623',
  wind: '#4da6ff',
  finance: '#34d399',
  signal: '#f43f5e',
} as const;

export type Theme = typeof S;