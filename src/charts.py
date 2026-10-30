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


def _highlight_colors(metros: pd.Series, highlight: list[str]) -> list[str]:
    return [config.ACCENT_COLOR if m in highlight else config.NEUTRAL_COLOR for m in metros]


def price_rent_scatter(markets: pd.DataFrame, highlight: list[str]) -> go.Figure:
    """Typical home value vs. typical rent, with dotted rent-to-price guide lines."""
    fig = go.Figure()
    max_price = markets["zhvi"].max() * 1.08
    for ratio in (0.004, 0.006):
        fig.add_trace(go.Scatter(
            x=[0, max_price], y=[0, max_price * ratio], mode="lines",
            line=dict(color=config.NEUTRAL_COLOR, dash="dot", width=1),
            name=f"{ratio:.1%} rent-to-price", hoverinfo="skip",
        ))
    is_selected = markets["metro"].isin(highlight)
    fig.add_trace(go.Scatter(
        x=markets["zhvi"], y=markets["zori"], mode="markers+text",
        text=markets["metro"].where(is_selected, ""), textposition="top center",
        marker=dict(size=12, color=_highlight_colors(markets["metro"], highlight), line=dict(color="white", width=1)),
        customdata=markets[["metro", "rent_to_price"]],
        hovertemplate="<b>%{customdata[0]}</b><br>Home value: $%{x:,.0f}<br>Rent: $%{y:,.0f}/mo"
                      "<br>Rent-to-price: %{customdata[1]:.2%}<extra></extra>",
        showlegend=False,
    ))
    fig.update_xaxes(title="Typical home value (Zillow ZHVI)", tickprefix="$", tickformat=",.0f", rangemode="tozero")
    fig.update_yaxes(title="Typical monthly rent (Zillow ZORI)", tickprefix="$", tickformat=",.0f", rangemode="tozero")
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    return _base_layout(fig, height=440)


def growth_affordability_scatter(scored: pd.DataFrame, highlight: list[str]) -> go.Figure:
    """Affordability pillar vs. growth pillar, split into quadrants at 50."""
    is_selected = scored["metro"].isin(highlight)
    fig = go.Figure(go.Scatter(
        x=scored["affordability_score"], y=scored["growth_score"], mode="markers+text",
        text=scored["metro"].where(is_selected, ""), textposition="top center",
        marker=dict(size=12, color=_highlight_colors(scored["metro"], highlight), line=dict(color="white", width=1)),
        customdata=scored[["metro"]],
        hovertemplate="<b>%{customdata[0]}</b><br>Affordability: %{x:.0f}<br>Growth: %{y:.0f}<extra></extra>",
    ))
    divider = dict(color=config.NEUTRAL_COLOR, dash="dot")
    fig.add_vline(50, line=divider)
    fig.add_hline(50, line=divider)
    corner = dict(showarrow=False, font=dict(size=11, color="#6B7280"))
    fig.add_annotation(x=98, y=102, text="Affordable and growing", xanchor="right", **corner)
    fig.add_annotation(x=2, y=102, text="Growing but pricey", xanchor="left", **corner)
    fig.add_annotation(x=98, y=-4, text="Affordable, slower growth", xanchor="right", **corner)
    fig.update_xaxes(title="Affordability score (higher = more affordable)", range=[-8, 108])
    fig.update_yaxes(title="Growth score", range=[-10, 108])
    return _base_layout(fig, height=440)


def pillar_grouped_bar(scored: pd.DataFrame) -> go.Figure:
    """Pillar scores side by side for each selected market."""
    fig = go.Figure()
    for pillar, label in config.PILLAR_LABELS.items():
        fig.add_trace(go.Bar(
            x=scored["metro"], y=scored[f"{pillar}_score"], name=label,
            marker_color=config.PILLAR_COLORS[pillar],
            hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:.0f}}<extra></extra>",
        ))
    fig.update_layout(barmode="group", legend=dict(orientation="h", y=1.12))
    fig.update_yaxes(title="Score (0-100)", range=[0, 105])
    return _base_layout(fig, height=400)
