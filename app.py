"""Multifamily Market Screener: page setup and tab routing only.

Run with: streamlit run app.py
"""

import streamlit as st

from src.data_loader import load_markets
from src.ui import comparison, rankings

st.set_page_config(page_title="Multifamily Market Screener", layout="wide")


@st.cache_data
def get_markets():
    return load_markets()


def main() -> None:
    markets, is_demo = get_markets()

    st.title("Multifamily Market Screener")
    st.caption("Compare U.S. metros for a 2-4 unit owner-occupied purchase, then test a specific property.")
    if is_demo:
        st.warning(
            "**Demo data in use.** These are fictional sample markets, not real metros. "
            "Build the real dataset with `python scripts/build_dataset.py`."
        )

    weights = rankings.weight_sidebar()
    selected = rankings.market_filter(markets)

    tab_rankings, tab_comparison, tab_calculator, tab_methodology = st.tabs(
        ["Market Rankings", "Market Comparison", "Property Calculator", "Methodology"]
    )
    with tab_rankings:
        rankings.render(selected, weights)
    with tab_comparison:
        comparison.render(selected, weights)
    with tab_calculator:
        st.info("Coming soon.")
    with tab_methodology:
        st.info("Coming soon.")

    st.divider()
    st.caption("Analytical screening tool, not financial advice.")


main()
