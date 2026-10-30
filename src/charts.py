"""Plotly figure builders. Each function takes data and returns a figure; no Streamlit."""

import pandas as pd
import plotly.graph_objects as go

import config

FONT = dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=13, color="#1C2430")


def _base_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        font=FONT,
        height=height,
        margin=dict(l=10, r=20, t=30, b=10),
        hoverlabel=dict(bgcolor="white"),
    )
    return fig


def ranking_bar(scored: pd.DataFrame) -> go.Figure:
    """Horizontal bars of composite score, best market at the top."""
    data = scored.sort_values("composite_score")
    hover = (
        "<b>%{y}</b><br>Composite: %{x:.1f}"
        "<br>Affordability: %{customdata[0]:.1f}"
        "<br>Growth: %{customdata[1]:.1f}"
        "<br>Rental demand: %{customdata[2]:.1f}<extra></extra>"
    )
    fig = go.Figure(go.Bar(
        x=data["composite_score"],
        y=data["metro"],
        orientation="h",
        marker_color=config.ACCENT_COLOR,
        text=data["composite_score"].round(0).astype("Int64"),
        textposition="outside",
        customdata=data[["affordability_score", "growth_score", "rental_demand_score"]],
        hovertemplate=hover,
    ))
    fig.update_xaxes(range=[0, 105], title="Composite score (0-100)", showgrid=True)
    fig.update_yaxes(title=None)
    return _base_layout(fig, height=max(320, 28 * len(data) + 60))
