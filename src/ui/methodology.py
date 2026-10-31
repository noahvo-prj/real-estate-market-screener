"""Methodology tab: formulas, scoring method, data sources, assumptions and limitations."""

import pandas as pd
import streamlit as st

import config

DISCLAIMERS = [
    "Historical appreciation does not guarantee future appreciation.",
    "Short-term rental rules vary by city and can prohibit short-term rentals entirely.",
    "Taxes and insurance vary widely, even within one metro.",
    "Rents can change.",
    "Loan eligibility and terms vary by borrower and lender.",
    "This is a screening tool, not financial advice.",
]


def _data_sources(markets: pd.DataFrame, is_demo: bool) -> None:
    st.markdown("### Data sources")
    if is_demo:
        st.warning("The app is showing the demo dataset: fictional markets with made-up numbers.")
    zillow_month = markets["zhvi_month"].iloc[0] if "zhvi_month" in markets else "n/a"
    sources = pd.DataFrame([
        ("Zillow Home Value Index (ZHVI)", "Typical home value; 5-yr home price growth",
         f"Monthly, latest {zillow_month}", "All homes, smoothed, seasonally adjusted"),
        ("Zillow Observed Rent Index (ZORI)", "Typical rent; 3-yr rent growth",
         f"Monthly, latest {zillow_month}", "All homes plus multifamily, smoothed"),
        ("Census ACS 1-year (API)", "Median household income, median home value, median real estate taxes, "
         "rental vacancy rate", str(config.ACS_YEAR), "Income growth compares with "
         f"{config.ACS_BASE_YEAR}; 2020 1-year data was not released"),
        ("Census Population Estimates", "Population and population growth",
         f"July {config.PEP_BASE_YEAR} to July {config.PEP_VINTAGE}", f"Vintage {config.PEP_VINTAGE} metro file"),
        ("VA.gov", "VA funding fee rates", "Effective April 7, 2023", "Checked October 28, 2026"),
    ], columns=["Source", "Used for", "Period", "Notes"])
    st.dataframe(sources, hide_index=True, width="stretch")
    st.caption(
        "Geography: metropolitan statistical areas (CBSAs), 2023 Census definitions. Zillow and Census data are "
        "joined by metro code. Missing values are left missing, never estimated."
    )


def _scoring() -> None:
    st.markdown("### Market scoring")
    st.markdown(
        "1. **Percentile rank** each metric across the selected markets, from 0 to 100. "
        "For metrics where lower is better, the order is flipped. "
        "An 80 means the market beats 80% of the other selected markets on that metric.\n"
        "2. **Average** the metric scores within each pillar to get a pillar score.\n"
        "3. **Composite score** = weighted sum of the three pillar scores, using the sidebar weights "
        "(which must total 100%).\n"
        "4. **Missing data:** a pillar is scored from the metrics that are available. If a whole pillar is "
        "missing, the remaining pillar weights are scaled up to 100%. Affected markets are flagged."
    )
    metrics = pd.DataFrame([
        (config.PILLAR_LABELS[m["pillar"]], m["label"], m["better"].capitalize())
        for m in config.METRICS.values()
    ], columns=["Pillar", "Metric", "Better if"])
    st.dataframe(metrics, hide_index=True, width="stretch")

    st.markdown("**Metric definitions**")
    st.markdown(
        "- **Rent-to-price:** monthly ZORI / ZHVI.\n"
        "- **Price-to-income:** ZHVI / median household income.\n"
        "- **Effective property tax rate:** median real estate taxes paid / median home value (both ACS). "
        "A ratio of medians, so an approximation.\n"
        "- **Growth rates:** compound annual growth, (end / start)^(1 / years) - 1. Income growth is nominal "
        "(not adjusted for inflation).\n"
        "- **Rental vacancy rate:** ACS rental vacancy rate, metro-wide."
    )

    st.markdown("**Weight presets**")
    presets = pd.DataFrame(
        {name: {config.PILLAR_LABELS[p]: f"{w:.0%}" for p, w in weights.items()}
         for name, weights in config.WEIGHT_PRESETS.items()}
    ).reset_index(names="Pillar")
    st.dataframe(presets, hide_index=True, width="stretch")

    st.markdown("**Why percentile ranks instead of min-max scaling?**")
    st.markdown(
        "With only a handful of markets, one outlier (for example, a very expensive coastal metro) squashes "
        "everyone else's min-max scores into a narrow band. Percentile ranks are robust to outliers and easy "
        "to explain. The trade-off: scores are relative to the markets chosen, not absolute. Adding or "
        "removing a market can change other markets' scores."
    )


def _formulas() -> None:
    st.markdown("### Property calculator formulas")
    st.markdown("**Monthly mortgage payment (principal and interest)**")
    st.latex(r"M = P \cdot \frac{r(1+r)^n}{(1+r)^n - 1}")
    st.caption("P = loan amount, r = annual rate / 12, n = years x 12. At 0% interest, M = P / n.")

    formulas = pd.DataFrame([
        ("Loan amount", "Price - down payment (+ VA funding fee if financed)"),
        ("VA funding fee", "Base loan x fee rate (depends on down payment and first vs. later use; 0 if exempt)"),
        ("Gross potential rent (GPR)", "Rent per unit x units rented x 12"),
        ("Effective rental income", "GPR x (1 - vacancy rate)"),
        ("Operating expenses", "Taxes + insurance + HOA + maintenance + capex + management + owner-paid "
                               "utilities + other. Excludes the mortgage."),
        ("Net operating income (NOI)", "Effective rental income - operating expenses"),
        ("Cap rate", "NOI / purchase price"),
        ("Monthly cash flow", "(Effective rental income - operating expenses) / 12 - monthly mortgage payment"),
        ("Debt service coverage ratio (DSCR)", "NOI / annual mortgage payments"),
        ("Break-even occupancy", "(Operating expenses + annual mortgage payments) / GPR"),
        ("Total cash needed at purchase", "Down payment + closing costs + funding fee (if paid in cash) + "
                                          "reserves + initial repairs + furnishing"),
        ("Cash-on-cash return", "Annual cash flow / total cash needed at purchase (investor view only)"),
        ("Owner's net housing cost", "Monthly mortgage + monthly operating expenses - monthly effective rent "
                                     "from the other units"),
    ], columns=["Metric", "Formula"])
    st.dataframe(formulas, hide_index=True, width="stretch")


def _assumptions() -> None:
    st.markdown("### Assumptions")
    st.markdown(
        "- **Two views of one property.** The investor view treats every unit as rented. The owner view counts "
        "rent only from the units the owner doesn't live in; the owner's unit is never counted as income. "
        "Costs are for the whole property in both views.\n"
        "- **Maintenance and capex** are a share of the whole building's potential rent, because the building "
        "wears out whether or not the owner lives in a unit. **Management** is a share of rent actually collected.\n"
        "- **Prefilled values** (price, rent, tax rate, vacancy) are metro-wide typical values and should be "
        "replaced with numbers for the actual property.\n"
        "- **The default interest rate is a placeholder**, not a current market rate.\n"
        "- **Projections** apply constant annual growth rates for value, rent and fixed expenses. They show what "
        "the assumptions imply; they are not forecasts.\n"
        "- **Sensitivity chart:** each input is moved down and up by a fixed amount while everything else stays "
        "the same: interest rate ±1 point, rent ±10%, vacancy ±5 points, taxes ±25%, insurance ±25%, "
        "maintenance ±2 points.\n"
        "- **Short-term rental scenario:** nightly rate x occupancy x 30.4 nights per month, minus platform fees, "
        "cleaning and supplies. It ignores extra insurance, licensing and lodging taxes."
    )


def _limitations() -> None:
    st.markdown("### Limitations")
    st.markdown(
        "- **Market metrics are proxies.** ZHVI mostly reflects single-family homes and ZORI covers all rental "
        "types. Neither is a duplex price or a duplex unit's rent. Use the property calculator with real "
        "listing and rent numbers to evaluate an actual deal.\n"
        "- **Scores are relative** to the markets selected, not an absolute measure of quality.\n"
        "- **Metro averages hide neighborhood differences.** Taxes, insurance, rents and vacancy vary a lot "
        "within a metro.\n"
        "- **Data years differ:** Zillow is monthly and current; Census ACS lags by about a year. ACS 1-year "
        "estimates also have margins of error that the scores don't show.\n"
        "- **Boundary changes:** Census metro definitions changed in 2023, so income growth (2019 to 2024) "
        "compares slightly different areas for a few metros, such as New York and Chicago. Cleveland's 2019 "
        "income uses the older Cleveland-Elyria definition.\n"
        "- **Lender qualification isn't modeled.** Lenders often count only part of projected rent (commonly "
        "around 75%) toward qualifying income, and owner-occupied VA loans are underwritten on debt-to-income "
        "ratio and residual income, not DSCR.\n"
        "- **Not included:** insurance cost data (flood and storm risk), employment data, short-term rental "
        "market data, military installations and housing allowance (BAH). See future improvements in the README."
    )


def render(markets: pd.DataFrame, is_demo: bool) -> None:
    st.subheader("Methodology")
    st.caption("How every number in this app is calculated, where the data comes from, and what it can't tell you.")
    _data_sources(markets, is_demo)
    _scoring()
    _formulas()
    _assumptions()
    _limitations()
    st.markdown("### Disclaimers")
    st.markdown("\n".join(f"- {d}" for d in DISCLAIMERS))
