"""Market Comparison tab: side-by-side view of 2-5 markets."""

import pandas as pd
import streamlit as st

import config
from src import charts, scoring

MAX_MARKETS = 5

# column -> (label, format)
RAW_ROWS = {
    "zhvi": ("Typical home value", "${:,.0f}"),
    "zori": ("Typical monthly rent", "${:,.0f}"),
    "median_household_income": ("Median household income", "${:,.0f}"),
    "rent_to_price": ("Rent-to-price ratio (monthly)", "{:.2%}"),
    "price_to_income": ("Price-to-income ratio", "{:.1f}x"),
    "effective_tax_rate": ("Effective property tax rate", "{:.2%}"),
    "home_price_growth": ("Home price growth (5-yr annualized)", "{:.1%}"),
    "population_growth": ("Population growth (5-yr annualized)", "{:.2%}"),
    "income_growth": ("Income growth (5-yr annualized)", "{:.1%}"),
    "rental_vacancy_rate": ("Rental vacancy rate", "{:.1%}"),
    "rent_growth": ("Rent growth (3-yr annualized)", "{:.1%}"),
}
SCORE_ROWS = {
    "affordability_score": "Affordability score",
    "growth_score": "Growth score",
    "rental_demand_score": "Rental demand score",
    "composite_score": "Composite score",
    "rank": "Rank",
}


def _format(value, fmt: str) -> str:
    return "n/a" if pd.isna(value) else fmt.format(value)


def comparison_table(scored: pd.DataFrame, selected: list[str]) -> pd.DataFrame:
    """Metrics as rows, chosen markets as columns, formatted for display."""
    data = scored.set_index("metro").loc[selected]
    rows = []
    for col, (label, fmt) in RAW_ROWS.items():
        better = config.METRICS.get(col, {}).get("better", "")
        rows.append({"Metric": label, "Better if": better, **{m: _format(data.at[m, col], fmt) for m in selected}})
    for col, label in SCORE_ROWS.items():
        if col in data:
            fmt = "{:.0f}" if col == "rank" else "{:.0f} / 100"
            rows.append({"Metric": label, "Better if": "higher" if col != "rank" else "lower",
                         **{m: _format(data.at[m, col], fmt) for m in selected}})
    return pd.DataFrame(rows)


def render(markets: pd.DataFrame, weights: dict[str, float] | None) -> None:
    st.subheader("Market Comparison")
    st.caption("Pick 2-5 markets to compare side by side. Scores are relative to the markets selected in the sidebar.")
    if len(markets) < 2:
        st.info("Select at least two markets in the sidebar to compare.")
        return

    # Pillar scores don't depend on the weights, so they can be shown even if weights are invalid.
    scored = scoring.score_markets(markets, weights or config.WEIGHT_PRESETS[config.DEFAULT_PRESET])
    if weights is None:
        scored = scored.drop(columns=["composite_score", "rank"])
        st.warning("Sidebar weights don't total 100%, so composite scores and ranks are hidden.")

    # Keep the user's picks across reruns (e.g. when weights change); drop any no longer available.
    options = scored["metro"].tolist()
    kept = [m for m in st.session_state.get("compare_markets", []) if m in options]
    st.session_state["compare_markets"] = kept if "compare_markets" in st.session_state else options[:3]
    selected = st.multiselect(
        "Markets to compare", options, key="compare_markets",
        max_selections=MAX_MARKETS, help="Starts with the top three ranked markets.",
    )
    if len(selected) < 2:
        st.info("Choose at least two markets.")
        return

    st.dataframe(comparison_table(scored, selected), hide_index=True, width="stretch")
    st.caption(
        "Home values and rents are Zillow metro-wide typical values (mostly single-family homes), "
        "not duplex prices or duplex rents. They are screening proxies."
    )

    left, right = st.columns(2)
    with left:
        st.markdown("#### Home price vs. rent")
        st.caption("Markets above a dotted line earn more rent per dollar of home price.")
        st.plotly_chart(charts.price_rent_scatter(scored, selected), width="stretch")
    with right:
        st.markdown("#### Growth vs. affordability")
        st.caption("The top-right corner is both affordable and growing, relative to the other markets.")
        st.plotly_chart(charts.growth_affordability_scatter(scored, selected), width="stretch")

    st.markdown("#### Pillar scores")
    chosen = scored.set_index("metro").loc[selected].reset_index()
    st.plotly_chart(charts.pillar_grouped_bar(chosen), width="stretch")
