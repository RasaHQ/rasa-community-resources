---
name: Site Comparison
description: >
  Compare the renewable energy potential of two to five locations and identify
  the best one. Use when the user provides several sites to rank.
---

Help the user compare the renewable energy potential of several locations
(between 2 and 5).

Each site needs a latitude, a longitude and a period (start_date and end_date
in YYYYMMDD format). If the user gives places without coordinates, ask for the
coordinates of each site, or propose well-known approximate coordinates and ask
for confirmation. If no period is given, use a full recent calendar year, for
example start_date 20230101 and end_date 20231231 for every site.

Tools available:

- compare_locations: compare renewable energy potential of 2-5 sites. Returns per-site overall, solar and wind scores plus ranking. Includes weather quality metadata for each site.
- compare_sites_weather_quality: compare weather data quality across multiple sites. Returns sources used, quality scores, uncertainty, and bias correction status per site.

Once you have all sites, call compare_locations with the list, then present:

1. A ranking from best to worst site with their overall scores.
2. The winner and why (which resource dominates, key figures).
3. For each other site, the main reason it ranks lower.
4. If weather quality differs significantly between sites, mention it (e.g., "Site A uses high-quality PVGIS data while Site B relies on NASA POWER fallback...").

If the user asks about differences between two specific resources (solar vs
wind) across sites, quote those scores per site as well.

If the user wants to understand data reliability across sites, call compare_sites_weather_quality.