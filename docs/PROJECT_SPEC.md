# Project Spec: Multifamily Market Screener / VA House-Hack Analyzer

## 1. Goal

Build a Python + Streamlit analytics app that helps a user:

1. Compare U.S. metro areas for buying a small multifamily property (2–4 units).
2. Evaluate a specific property for owner-occupied house hacking, including with a VA loan.

**Core question:** Which markets offer the best combination of affordability, growth, and rental demand for a multifamily owner-occupant, and does a specific property make financial sense?

This is a **portfolio project** for roles in data analytics, FP&A, finance, BI, risk analytics, and real estate analytics. It should look like an analyst-built decision tool, not a coding tutorial.

The app must never claim that any market is guaranteed to appreciate or that any property is guaranteed to be profitable. It is a screening tool, not financial advice.

## 2. Scope decisions (already made)

**In scope for v1**
- Market rankings with adjustable weights
- Market comparison (2–5 markets)
- Property calculator with investor view and owner-occupant view
- Methodology tab
- Real data from Zillow and the U.S. Census Bureau, with a labeled demo dataset as a fallback
- Unit tests for all finance and scoring functions
- README and data dictionary

**Cut or deferred**
- Airbnb/STR data in the market score. Coverage is patchy, paid sources can't be redistributed, and regulations vary city by city. It is replaced by an optional STR scenario in the calculator.
- Military installation and BAH analysis (future work)
- Radar charts (hard to read)
- Machine learning or forecasting models (not needed; explainability matters more)
- Geospatial mapping (future work)

## 3. Tech stack

- Python 3.11+
- pandas, NumPy
- Streamlit
- Plotly
- pytest
- python-dotenv and requests (for the Census API)

No other frameworks.

## 4. Project structure

```
real-estate-market-screener/
├── app.py                    # thin: page setup and tab routing only
├── config.py                 # default assumptions, weight presets, metric directions
├── requirements.txt
├── README.md
├── .gitignore                # must include .env
├── .env                      # CENSUS_API_KEY (never committed)
├── docs/
│   └── PROJECT_SPEC.md
├── data/
│   ├── raw/                  # Zillow CSVs, Census API pulls
│   ├── processed/markets.csv # output of the pipeline
│   ├── demo/markets_demo.csv # clearly labeled sample data
│   └── data_dictionary.md
├── scripts/
│   └── build_dataset.py      # raw → processed pipeline
├── src/
│   ├── calculations.py       # finance functions (no Streamlit)
│   ├── scoring.py            # market scoring (no Streamlit)
│   ├── data_loader.py        # load and validate data, demo fallback
│   ├── charts.py             # Plotly figure builders
│   └── ui/
│       ├── rankings.py
│       ├── comparison.py
│       ├── calculator.py
│       └── methodology.py
├── tests/
│   ├── test_calculations.py
│   └── test_scoring.py
└── assets/screenshots/
```

**Rule:** `src/calculations.py` and `src/scoring.py` never import Streamlit. Business logic stays separate from the UI so it can be tested.

## 5. Data

### Geography
Metro areas (CBSAs). Zillow and the Census both use metro definitions, which lets the datasets be joined. Target 15–20 metros chosen for a mix of price levels and regions.

### Sources

| Source | Data | How to get it |
|---|---|---|
| Zillow Home Value Index (ZHVI), All Homes, smoothed, seasonally adjusted, Metro & U.S. | Typical home value, monthly history | Manual download to `data/raw/zillow_zhvi_metro.csv` |
| Zillow Observed Rent Index (ZORI), All Homes Plus Multifamily, smoothed, Metro & U.S. | Typical rent, monthly history | Manual download to `data/raw/zillow_zori_metro.csv` |
| Census American Community Survey (ACS) 1-year, metro level | Median household income, rental vacancy rate, median home value, median real estate taxes paid | Census API using `CENSUS_API_KEY` from `.env` |
| Census Population Estimates | Population by year | Census API |

### Rules
- Every column in `markets.csv` is documented in `data_dictionary.md` with its source, year, geography, and how it was calculated.
- Never fabricate current values. If a value is missing, leave it missing and handle it in the code.
- Demo data must be clearly labeled as demo everywhere it appears, including a visible banner in the app.
- Don't scrape websites that prohibit it.

### Known limitation to document
ZHVI is mostly single-family homes and ZORI covers all rental types. Neither is a duplex price or a duplex unit's rent. Market metrics are therefore **proxies** for screening, and the property calculator is where a real deal gets evaluated.

## 6. Market scoring

### Metrics (each used in only one pillar)

| Pillar | Default weight | Metric | Better if |
|---|---|---|---|
| Affordability / cash flow | 40% | Rent-to-price ratio (monthly ZORI ÷ ZHVI) | Higher |
| | | Price-to-income ratio (ZHVI ÷ median household income) | Lower |
| | | Effective property tax rate (median taxes ÷ median home value) | Lower |
| Growth | 30% | 5-year annualized home price growth | Higher |
| | | Population growth (multi-year) | Higher |
| | | Median household income growth | Higher |
| Rental demand | 30% | Rental vacancy rate | Lower |
| | | Rent growth (1-year or multi-year, documented) | Higher |

### Method
1. **Percentile rank** each metric across the selected markets (0 to 100). Flip the direction for "lower is better" metrics.
2. Average the metric scores within each pillar to get a pillar score.
3. Composite score = weighted sum of pillar scores (0 to 100).
4. Weights are adjustable in the sidebar and must sum to 100%.
5. Missing values: score the pillar using the available metrics and flag the market.

**Why percentile ranks instead of min-max scaling:** with a small number of markets, one outlier squashes everyone else's min-max scores. Percentile ranks are robust and easy to explain: "an 80 means this market beats 80% of the comparison set on this metric." The tradeoff is that scores are relative to the markets chosen, not absolute.

### Weight sensitivity
Three presets:
- **Cash-flow focused:** 60 / 20 / 20
- **Balanced:** 40 / 30 / 30 (default)
- **Growth focused:** 20 / 50 / 30

Show how each market's rank changes across presets. This answers "what could cause the ranking to change?"

## 7. Property calculator

### City prefill
Selecting a market prefills:
- Rent per unit (ZORI)
- Property tax rate (Census)
- Vacancy rate (Census)
- Purchase price (ZHVI), with a visible warning that it reflects mostly single-family homes and should be replaced with a real listing price

Every prefilled value shows its source. Every value is editable.

### Inputs

**Property:** purchase price, number of units (2–4), owner-occupied units (default 1), monthly rent per rentable unit, market rent for a comparable unit (for the rent-vs-own comparison)

**Financing:** VA loan toggle, down payment, interest rate, loan term, VA funding fee (look up the current VA.gov fee table; do not use memory), finance the funding fee into the loan vs. pay in cash, funding fee exemption toggle, closing costs

**Operating costs:** property tax rate, annual insurance, monthly HOA, vacancy %, maintenance % of rent, capital expenditure reserve % of rent, property management % (default 0% if self-managed), owner-paid utilities, other monthly expenses

**Upfront cash:** reserves, initial repairs, furnishing (if STR)

**Projection (optional):** appreciation rate, rent growth rate, expense growth rate, years to project (5–10)

**Optional STR scenario (one unit):** nightly rate, occupancy %, cleaning and platform fees, extra utilities and supplies. Include a note that STR legality must be checked locally.

### Formulas

| Metric | Formula |
|---|---|
| Loan amount | Price − down payment (+ funding fee if financed) |
| Monthly P&I | M = P × [r(1+r)^n] / [(1+r)^n − 1]; P = loan amount, r = annual rate ÷ 12, n = years × 12. If r = 0, M = P ÷ n |
| Gross potential rent (GPR) | Rent per unit × number of units considered × 12 |
| Effective rental income | GPR × (1 − vacancy rate) |
| Operating expenses | Taxes + insurance + HOA + maintenance + capex reserve + management + owner-paid utilities + other. **Excludes** mortgage P&I |
| NOI | Effective rental income − operating expenses |
| Cap rate | NOI ÷ purchase price |
| Monthly cash flow | (Effective rental income − operating expenses) ÷ 12 − monthly P&I |
| DSCR | NOI ÷ annual debt service |
| Break-even occupancy | (Operating expenses + annual debt service) ÷ GPR |
| Total cash needed at purchase | Down payment + closing costs + funding fee (if paid in cash) + reserves + initial repairs + furnishing |
| Cash-on-cash return | Annual cash flow ÷ total cash needed at purchase (investor view only, definition shown in app) |

Percentage convention: store as decimals in code (0.07), display as percentages in the UI (7.0%).

### Two views of the same property

**Investor view (as if all units are rented):**
GPR, effective rental income, operating expenses, NOI, cap rate, monthly and annual cash flow, DSCR, break-even occupancy, cash-on-cash return.

**Owner-occupant view (house hack):**
Rental income comes only from the non-owner units. Costs are for the whole property, including mortgage.

- Owner's net monthly housing cost = monthly P&I + monthly operating expenses − monthly effective rent from other units
- Comparison: net housing cost vs. market rent for a comparable unit
- Headline: "You'd pay about $X/month to live here vs. $Y renting a similar unit."

### Terminology rules
- NOI and cap rate exclude debt service. Explain this in the app.
- Owner occupancy is not rental income. Never count the owner's unit as rent in the owner view.
- DSCR is shown in the investor view only, with a note that owner-occupied VA loans are underwritten on the borrower's debt-to-income ratio, not DSCR.
- 0% down does not mean $0 invested. The itemized "total cash needed" makes this visible.
- Lenders often count only part of projected rent toward loan qualification. Note this in the methodology; don't model it.

### Multi-year projection
A table and chart for 5–10 years: property value, loan balance, equity, annual cash flow, cumulative cash flow. Clearly labeled as assumption-driven, not a forecast.

### Sensitivity chart
A tornado chart showing how much the owner's monthly cost (or investor cash flow) changes when each key input moves up or down (interest rate, rent, vacancy, taxes, insurance, maintenance).

## 8. App layout

Four tabs:
1. **Market Rankings:** weight sliders and presets in the sidebar, ranked horizontal bar chart, sortable table with pillar scores, rank-sensitivity table
2. **Market Comparison:** select 2–5 markets; comparison table; home price vs. rent scatter; growth vs. affordability scatter; grouped bar chart of pillar scores
3. **Property Calculator:** inputs in the sidebar or expanders, big metric cards at top, investor and owner views side by side, cash-needed breakdown, projection, tornado chart
4. **Methodology:** every formula, scoring method, weights, data sources and years, assumptions, limitations

### Style
- Clean, professional, one or two accent colors, plenty of white space
- Metric cards for headline numbers
- Plain-English labels, with technical terms in tooltips
- No excessive emojis, flashy colors, or animations
- Visible banner when demo data is in use
- Footer: "Analytical screening tool, not financial advice."

## 9. Disclaimers the app must show
- Historical appreciation does not guarantee future appreciation.
- Short-term rental rules vary by city and can prohibit STR entirely.
- Taxes and insurance vary widely, even within one metro.
- Rents can change.
- Loan eligibility and terms vary by borrower and lender.
- This is a screening tool, not financial advice.

## 10. Code quality
- Readable names, docstrings on important functions, minimal useful comments
- No monolithic `app.py`
- Validate inputs: no negative prices, percentages between 0 and 100, owner units fewer than total units
- Handle division by zero and missing data without crashing
- Defaults live in `config.py`, not scattered in the code
- Tests cover: mortgage payment against a known value, 0% interest, 100% vacancy, zero rentable units, financed vs. cash funding fee, percentile scoring direction, weights summing to 100, missing values

## 11. Build order

Work one step at a time. Explain each step in plain English and wait for confirmation before moving on.

1. Git setup, `.gitignore`, `requirements.txt`, folder structure
2. `calculations.py` and tests
3. Data pipeline (`build_dataset.py`) and demo dataset
4. `scoring.py` and tests
5. Streamlit tabs and charts
6. Edge cases and UI polish
7. README and data dictionary (with screenshots)
8. Deploy to Streamlit Community Cloud
9. Final review as a data analytics hiring manager, an FP&A hiring manager, and a real estate analyst

## 12. Final deliverables
1. Working Streamlit app with a live link
2. Clean public GitHub repo
3. `requirements.txt`
4. `README.md` with screenshots
5. Methodology tab
6. Market dataset with documented sources
7. Property calculator
8. Weighted market ranking with sensitivity presets
9. Professional visualizations
10. Two resume bullets
11. 60-second interview explanation
12. 3-minute technical explanation
13. Limitations and future improvements

**Never invent results or performance metrics for resume bullets. Only claim what was actually built and calculated.**

## 13. Interview readiness

For every major decision, be ready to explain:
- Why this metric, formula, weight, and normalization method?
- What assumptions and biases exist? What data is missing?
- What could change the ranking?
- Why is historical appreciation imperfect?
- Why might cash flow and appreciation conflict?
- How should STR rules affect the analysis?
- How does owner occupancy change the financial analysis?

## 14. Future improvements
- STR market data where licensed data is available
- Military installation proximity and BAH-based rental demand
- BLS employment growth
- Insurance cost data (especially flood and storm risk)
- Map view
- FHA comparison (3–4 unit self-sufficiency test)
