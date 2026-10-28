# Four real-source cards: implementation target


Operator decision v3, 22 October 2026, supersedes the constructed-only primary route. This records the selected sources and terms assessment; it does not attest that the adapters, released Core install or live smoke have passed. Core receives the adapters first. The frozen74adca16 REPLAY class remains the separate fallback.

| Card | Keyless source | Terms and attribution |
| --- | --- | --- |
| Weather | MET Norway Locationforecast compact JSON, `https://api.met.no/weatherapi/locationforecast/2.0/compact` with destination coordinates | [Provider licensing](https://api.met.no/doc/License) applies CC BY4.0; [terms](https://api.met.no/doc/TermsOfService) require identification, caching and responsible traffic. Credit MET Norway, CC BY4.0, and identify normalisation. |
| Flight | `https://api.adsb.lol/v2/callsign/{callsign}`; documented read-only route lookup using POST `https://api.adsb.lol/api/0/routeset` | [Official API terms](https://api.adsb.lol/docs): free API, public data ODbL. [Official route implementation](https://github.com/adsblol/api/blob/main/src/adsb_api/utils/api_routes.py) uses Virtual Radar Server standing data, whose [CC0 licence](https://github.com/vradarserver/standing-data/blob/main/LICENSE) permits commercial reuse. Credit ADSB.lol contributors, ODbL1.0, and Virtual Radar Server standing-data, CC0. A plausible route is not airline confirmation. |
| Arrival timeline | Local calculation from validated flight estimate, traveller-stated transfer and meeting time | Label computed; retain flight provenance and label transfer ASSUMPTION. No timeline API or number from model prose. |
| Market | ECB daily EUR reference FX, `https://data-api.ecb.europa.eu/service/data/EXR/D.USD+GBP.EUR.SP00.A?lastNObservations=2&format=csvdata` | [ECB reuse policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html) permits commercial/non-commercial reuse with source citation. [Copyright conditions](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html) require accurate reproduction and identification of modifications; paid materials must tell users that ECB data are freely available. Credit ECB statistics. |

The [ECB query documentation](https://data.ecb.europa.eu/help/api/data-examples) supports bounded currency selection, recent observations and CSV. Keep actual daily observation dates. Label the card **daily reference rate, not a live quote**; compute changes only from actual observations and identify that calculation. Do not invent an intraday publication time.

Flight arrival is computed from fresh observed position, ground speed and great-circle distance to the route destination: **computed from live position, not an airline time**. Scheduled times stay “not provided” when absent. Neither “on time” nor “delayed” is inferred. Missing position, route, speed or usable data makes the affected calculation unavailable. No fixture fills a live-source gap.

## Outbound boundary

Service hosts only:

- `api.met.no`
- `api.adsb.lol`
- `data-api.ecb.europa.eu`

Identifying User-Agent: `RasaCommunityFlightBriefing/1.0 (+https://rasa.community)`.

The adapters must refuse other hosts, userinfo, non-HTTPS URLs, unexpected ports, IP literals, lookalikes and redirects before a second connection. No environment proxy routing. Cache identical source requests for at least60 seconds and until a provider's later expiry; honour Retry-After and apply bounded pacing. A failed refresh never silently returns expired data. No HTML scraping. No personal passenger, crew or registration-owner fields are retained.

The browser loads only `http://127.0.0.1:8942/cards` and its local refresh. It never calls a provider or loads a remote font, script, image or stylesheet. Render only Core-validated DataRefs. Every card must retain source, attribution and fetch time; a card never mixes live and fixture values.

### Provenance and freshness are separate

The 22 October card-label ruling clarifies decision v3. Each displayed value has exactly one provenance label: **PROVIDER DATA**, **COMPUTED** (with its inputs named), or **REPLAY**. Provider and computed values also have exactly one freshness line: **live**, **daily reference rate, not a live quote**, or **delayed**. REPLAY values have no freshness line.

Map the validated fields rather than source text: `replay=true` means REPLAY; otherwise the source observation is PROVIDER DATA. The validated assumption label `estimated_arrival_from_live_position` marks the derived arrival as COMPUTED. `rate_basis=daily_reference` selects the daily reference line; `delayed=true` selects delayed; otherwise live applies to current observations and forecast runs. The daily ECB publication date stays visible. No daily or delayed value is labelled live.

Acceptance must include the named mutant that substitutes live freshness for a daily-reference value. This document states the required mapping; actual renderer and adapter acceptance remain pending.

adsbdb is not selected: its public route-data notice restricts copying, publication and incorporation without permission. No rights are inferred from a free endpoint or from software licensing alone.

## Outstanding acceptance

Actual Core source-adapter coverage and receiving compatibility, nullable missing schedule/probability fields and explicit provenance/date metadata, recorded-response tests with named failing mutants, live keyless smoke, published Core renderer/adapters, regenerated PyPI locks, screenshots and the independent class fresh clone remain required. The market card is a finished second-act checkpoint, not specification-only work.
