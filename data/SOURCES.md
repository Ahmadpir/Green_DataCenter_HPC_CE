# Data sources (all public, no account or API key)

All files were downloaded on **2026-10-18** by `code/src/fetch_data.py` and reduced to hourly UTC values.

| File | Source | URL / request | Licence / terms | Used for |
|---|---|---|---|---|
| `energycharts_public_power_{ie,uk,nl,be,dk,fi,de,fr,pl}_2025_hourly.csv.gz` | Energy-Charts API, Fraunhofer ISE, endpoint `/public_power` (net public generation by production type, MW, 15-min or hourly, averaged to hourly) | `https://api.energy-charts.info/public_power?country={cc}&start=2025-01-01T00:00Z&end=2025-12-31T23:59Z` | CC BY 4.0, attribution "Energy-Charts.info" | Hourly life-cycle carbon intensity for IE, NL, BE, DK, FI, DE, FR, PL |
| `neso_gb_carbon_intensity_2025_hourly.csv` | NESO (formerly National Grid ESO) Carbon Intensity API, national `actual` intensity, half-hourly averaged to hourly | `https://api.carbonintensity.org.uk/intensity/{from}/{to}` (13-day chunks) | Public API; see NESO terms of use | Carbon intensity for the UK region |
| `energinet_dk_co2emis_2025_hourly.csv` | Energinet Energi Data Service, dataset `CO2Emis` (5-min CO2 per kWh consumed, DK1/DK2, 125% heat method, includes exchange) | `https://api.energidataservice.dk/dataset/CO2Emis?start=2025-01-01T00:00&end=2026-01-01T00:00&timezone=UTC&columns=Minutes5UTC,PriceArea,CO2Emission&limit=0` | Energinet open data | Cross-check of our DK series only |
| (values in `config/params.yaml`) | Google, "Data center efficiency", per-campus trailing-twelve-month PUE, Q4 2025 | https://www.google.com/about/datacenters/efficiency/ | Public web page | PUE of IE (Dublin 1.08), NL (Eemshaven 1.07), BE (St. Ghislain 1.08), DK (Fredericia 1.07), FI (Hamina 1.10); the same page quotes the Uptime Institute 2025 survey average PUE of 1.54 used for UK, DE, FR, PL |
| (values in `config/params.yaml`) | IPCC AR5 WGIII Annex III, Table A.III.2 (Schloemer et al., 2014), life-cycle emission factors (min/median/max) | https://www.ipcc.ch/report/ar5/wg3/ | IPCC | Emission factor per production type |

## Known data issues (reported in the article)
- Energy-Charts' UK series contains only oil, gas, onshore wind and "others" (no nuclear, coal, solar, offshore wind or biomass), so it was **not** used; the UK region uses the NESO series (different method: GB generation mix incl. imports, NESO factors).
- Energy-Charts' Ireland series has no solar or biomass entry, so IE intensity is likely overstated.
- Intensity is production-based (imports ignored) except for the UK.
- Small gaps (IE 20 h, DK 4 h, FR 5 h of 8,760) were filled by time interpolation.
- An Energy-Charts `/co2eq` endpoint also responds but is not documented in the API specification, so it was not used.
- EIA-930 (US) per-balancing-authority files were reachable but 38-114 MB each, so US regions were left out to keep downloads small.
