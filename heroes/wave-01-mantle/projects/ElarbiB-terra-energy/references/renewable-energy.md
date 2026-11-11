# Renewable Energy Assessment — Reference Knowledge

## Solar metrics

### GHI — Global Horizontal Irradiance
Total solar radiation received on a horizontal surface, in kWh/m²/day.
Interpretation for photovoltaic viability:
- < 3.0 kWh/m²/day: low potential (high latitudes, cloudy climates)
- 3.0 – 4.5: moderate
- 4.5 – 6.0: good (most of the Mediterranean, southern USA, China)
- \> 6.0: excellent (Sahara, Middle East, Atacama, Australia)

### DNI — Direct Normal Irradiance
Direct beam radiation on a surface perpendicular to the sun. Key metric for
concentrated solar power (CSP) and CPV. High DNI (> 5.5 kWh/m²/day) with low
diffuse share indicates clear-sky climates.

### Performance Ratio (PR)
Ratio of actual PV output to theoretical output at standard test conditions.
- 0.80 – 0.90: well-designed system (typical range)
- < 0.75: thermal losses, shading, soiling or converter inefficiency
- > 0.90: excellent (cool climate, good ventilation)

### Specific yield
Annual production per installed kWp, in kWh/kWp/year.
- < 1000: weak site
- 1000 – 1400: average (Central Europe)
- 1400 – 1800: good
- \> 1800: excellent (desert, high altitude)

## Wind metrics

### Wind speed at hub height
Extrapolated from 2 m/10 m/50 m NASA POWER measurements with the power law
(shear exponent ≈ 0.14) to the turbine hub height.
- < 4.0 m/s: not viable for wind power
- 4.0 – 6.0 m/s: marginal, small wind only
- 6.0 – 8.0 m/s: good for onshore turbines
- \> 8.0 m/s: excellent

### Weibull distribution (k, c)
Models the wind speed frequency distribution. Shape k ≈ 2 means a Rayleigh
distribution (typical); k < 1.5 means very variable winds; k > 3 means steady
trade winds. Scale c is the characteristic speed — higher c shifts the
distribution toward stronger winds.

### Wind Power Density
Available energy per m² of swept area at hub height, in W/m².
- < 200 W/m²: poor
- 200 – 400: fair
- 400 – 700: good
- \> 700: excellent

### Capacity Factor (CF)
Actual annual production / maximum theoretical production.
Onshore wind: 0.20 – 0.25 marginal, 0.30 – 0.40 good, > 0.45 excellent.
Solar PV: 0.10 – 0.15 temperate, 0.18 – 0.25 sunny climates.

## Hybrid systems

### Complementarity score
Correlation quality between solar and wind production profiles over the year
(0–100). A high score (> 60) means solar and wind compensate each other
seasonally and daily, smoothing combined output and reducing storage needs.

### P50 / P90
P50 = median expected annual production; P90 = production exceeded with 90 %
probability (conservative estimate used for financing).

## Scoring

TerraEnergy scores each resource 0–100:
- 0–29: unsuitable
- 30–49: moderate
- 50–69: good
- 70–100: excellent

The overall score weights solar and wind scores by their production shares;
the dominant resource is the one contributing most of the estimated output.
