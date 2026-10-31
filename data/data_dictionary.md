# Data Dictionary

Every column in `data/processed/markets.csv`, produced by `scripts/build_dataset.py`.

**Geography:** metropolitan statistical areas (CBSAs), 2023 Census delineations. Zillow and Census
data are joined on `cbsa_code` using the metro list in `config.py`.
**Units:** money in nominal U.S. dollars. Rates and ratios are decimals (`0.05` = 5%).
**Missing values** are left blank. Nothing is filled in or estimated.

## Identifiers

| Column | Description | Source | Period |
|---|---|---|---|
| `metro` | Short metro name, as used by Zillow (e.g. "Dallas, TX") | Zillow `RegionName` | — |
| `cbsa_code` | Census metro code (CBSA), used as the join key | Census | 2023 definitions |
| `census_name` | Full Census metro name | Census ACS API `NAME` | 2024 |
| `zhvi_month` | Month of the latest Zillow values used | Zillow | e.g. `2026-09` |
| `acs_year` | Year of the ACS 1-year estimates used | Census ACS | 2024 |
| `data_source` | `real` for this file; `demo` in the demo dataset | Pipeline | — |

## Raw values

| Column | Description | Source | Period |
|---|---|---|---|
| `zhvi` | Typical home value. Zillow Home Value Index, all homes, smoothed, seasonally adjusted | Zillow ZHVI | Latest month (`zhvi_month`) |
| `zori` | Typical monthly rent. Zillow Observed Rent Index, all homes plus multifamily, smoothed | Zillow ZORI | Latest month (`zhvi_month`) |
| `median_household_income` | Median household income (variable `B19013_001E`) | Census ACS 1-year | 2024 |
| `median_home_value_acs` | Median value of owner-occupied homes (`B25077_001E`) | Census ACS 1-year | 2024 |
| `median_real_estate_taxes` | Median real estate taxes paid by owners (`B25103_001E`) | Census ACS 1-year | 2024 |
| `population` | Resident population estimate, July 1 | Census Population Estimates, vintage 2025 metro file | July 2025 |

## Scoring metrics

| Column | Pillar | Better if | Calculation | Sources |
|---|---|---|---|---|
| `rent_to_price` | Affordability | Higher | `zori / zhvi` (monthly rent / home value) | Zillow |
| `price_to_income` | Affordability | Lower | `zhvi / median_household_income` | Zillow, ACS 2024 |
| `effective_tax_rate` | Affordability | Lower | `median_real_estate_taxes / median_home_value_acs` | ACS 2024 |
| `home_price_growth` | Growth | Higher | 5-year compound annual growth of ZHVI: `(latest / value 60 months earlier)^(1/5) - 1` | Zillow |
| `population_growth` | Growth | Higher | Compound annual growth, July 2020 to July 2025: `(pop2025 / pop2020)^(1/5) - 1` | Census Population Estimates |
| `income_growth` | Growth | Higher | Compound annual growth of median household income, 2019 to 2024: `(inc2024 / inc2019)^(1/5) - 1`. Nominal, not inflation-adjusted | ACS 2019 and 2024 |
| `rental_vacancy_rate` | Rental demand | Lower | ACS rental vacancy rate (`DP04_0005E`) / 100 | ACS 2024 profile table |
| `rent_growth` | Rental demand | Higher | 3-year compound annual growth of ZORI: `(latest / value 36 months earlier)^(1/3) - 1` | Zillow |

## Notes and caveats

- **Proxies, not duplex values.** ZHVI mostly reflects single-family homes; ZORI covers all rental
  types. Neither is a duplex price or a duplex unit's rent.
- **Mixed periods.** Zillow values are monthly and current; ACS values lag by about a year.
- **Ratio of medians.** `effective_tax_rate` divides two medians, so it approximates the typical
  tax rate rather than measuring it directly.
- **Income growth base year.** The 2020 ACS 1-year release was not published in standard form
  (pandemic data-collection problems), so income growth compares 2019 with 2024.
- **Boundary changes.** Census metro definitions changed in 2023. Most metros kept their code but some
  changed shape (for example, New York no longer includes its Pennsylvania counties and Chicago no
  longer includes its Wisconsin county), so 2019-to-2024 income growth compares slightly different
  areas for a few metros. Cleveland's code itself changed: its 2024 code is 17410;
  its 2019 income comes from the older Cleveland-Elyria metro (17460). See `cbsa_code_base_year`
  in `config.py`.
- **Sampling error.** ACS 1-year estimates have margins of error that are not shown or used.

## Raw files (`data/raw/`, not committed)

| File | How it's obtained |
|---|---|
| `zillow_zhvi_metro.csv` | Manual download from [Zillow Research Data](https://www.zillow.com/research/data/): ZHVI, All Homes (SFR, Condo/Co-op), Smoothed, Seasonally Adjusted, Metro & U.S. |
| `zillow_zori_metro.csv` | Manual download from Zillow Research Data: ZORI, All Homes Plus Multifamily, Smoothed, Metro & U.S. |
| `census_acs1_*.json` | Downloaded by the pipeline from the Census API (needs `CENSUS_API_KEY`) |
| `census_pep_cbsa_v2025.csv` | Downloaded by the pipeline from census.gov (Population Estimates, metro totals) |

## Demo dataset (`data/demo/markets_demo.csv`)

Same columns, with ten **fictional** markets ("Demo City A (sample)" and so on) and made-up values.
It is used only when the real dataset is missing or invalid, and the app shows a banner whenever
it is in use. Demo City J has missing values on purpose, to exercise missing-data handling.
