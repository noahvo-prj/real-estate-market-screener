"""Market Rankings tab and the sidebar weight controls."""

import pandas as pd
import streamlit as st

import config
from src import charts, scoring

CUSTOM = "Custom"


def _set_weights_from_preset() -> None:
    preset = st.session_state["preset"]
    if preset in config.WEIGHT_PRESETS:
        for pillar, weight in config.WEIGHT_PRESETS[preset].items():
            st.session_state[f"weight_{pillar}"] = round(weight * 100)


def _mark_custom() -> None:
    st.session_state["preset"] = CUSTOM


def weight_sidebar() -> dict[str, float] | None:
    """Preset picker and weight sliders. Returns weights as decimals, or None if they don't sum to 100%."""
    if "preset" not in st.session_state:
        st.session_state["preset"] = config.DEFAULT_PRESET
        _set_weights_from_preset()

    st.sidebar.header("Market score weights")
    st.sidebar.selectbox(
        "Preset", [*config.WEIGHT_PRESETS, CUSTOM], key="preset", on_change=_set_weights_from_preset,
        help="Pick a preset, or move the sliders to set your own weights.",
    )
    for pillar, label in config.PILLAR_LABELS.items():
        st.sidebar.slider(f"{label} (%)", 0, 100, step=5, key=f"weight_{pillar}", on_change=_mark_custom)

    total = sum(st.session_state[f"weight_{p}"] for p in config.PILLAR_LABELS)
    if total != 100:
        st.sidebar.error(f"Weights add up to {total}%. Adjust them to total 100%.")
        return None
    st.sidebar.caption("Weights total 100%.")
    return {p: st.session_state[f"weight_{p}"] / 100 for p in config.PILLAR_LABELS}


def market_filter(markets: pd.DataFrame) -> pd.DataFrame:
    """Sidebar control for which markets are in the comparison set."""
    st.sidebar.header("Markets")
    all_metros = markets["metro"].tolist()
    chosen = st.sidebar.multiselect(
        "Markets included in scoring", all_metros, default=all_metros,
        help="Scores are relative: each market is compared only with the markets selected here.",
    )
    return markets[markets["metro"].isin(chosen)]


def render(markets: pd.DataFrame, weights: dict[str, float] | None) -> None:
    st.subheader("Market Rankings")
    st.caption(
        "Which metros look strongest for a 2-4 unit owner-occupant, based on the weights in the sidebar? "
        "Scores are relative to the markets selected: an 80 means the market beats 80% of them."
    )
    if weights is None:
        st.warning("Set the sidebar weights to total 100% to see the rankings.")
        return
    if len(markets) < 2:
        st.info("Select at least two markets in the sidebar to compare.")
        return

    scored = scoring.score_markets(markets, weights)
    top = scored.iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Top-ranked market", top["metro"])
    col2.metric("Top composite score", f"{top['composite_score']:.0f} / 100")
    col3.metric("Markets compared", len(scored))

    st.plotly_chart(charts.ranking_bar(scored), width="stretch")

    st.markdown("#### Scores by pillar")
    table = scored[["rank", "metro", "composite_score", "affordability_score", "growth_score",
                    "rental_demand_score", "missing_metrics"]]
    score_col = lambda label, help_text: st.column_config.ProgressColumn(
        label, min_value=0, max_value=100, format="%.0f", help=help_text
    )
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "rank": st.column_config.NumberColumn("Rank", width="small"),
            "metro": "Metro",
            "composite_score": score_col("Composite", "Weighted sum of the three pillar scores."),
            "affordability_score": score_col("Affordability", "Rent-to-price, price-to-income, property tax rate."),
            "growth_score": score_col("Growth", "Home price, population and income growth."),
            "rental_demand_score": score_col("Rental demand", "Rental vacancy rate and rent growth."),
            "missing_metrics": st.column_config.TextColumn(
                "Missing data", help="Metrics without data. The pillar is scored from the metrics that are available."
            ),
        },
    )
    if scored["has_missing_data"].any():
        st.caption("Markets with missing data are scored on the metrics they have. See the Missing data column.")

    st.markdown("#### What could change the ranking?")
    st.caption(
        "Each market's rank under the three weight presets. A large rank range means the result depends "
        "heavily on what you prioritize; a small range means the market ranks similarly either way."
    )
    st.dataframe(
        scoring.rank_sensitivity(markets),
        hide_index=True,
        width="stretch",
        column_config={
            "metro": "Metro",
            "Rank range": st.column_config.NumberColumn(
                "Rank range", help="Worst rank minus best rank across the three presets."
            ),
        },
    )
