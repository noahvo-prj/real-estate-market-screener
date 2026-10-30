"""Tests for src/scoring.py. Run with: pytest"""

import numpy as np
import pandas as pd
import pytest

import config
from src import scoring

BALANCED = config.WEIGHT_PRESETS["Balanced"]


def make_markets() -> pd.DataFrame:
    """Three markets where A is best on every metric and C is worst."""
    return pd.DataFrame({
        "metro": ["A", "B", "C"],
        "rent_to_price": [0.006, 0.005, 0.004],
        "price_to_income": [3.0, 4.0, 5.0],
        "effective_tax_rate": [0.005, 0.010, 0.015],
        "home_price_growth": [0.06, 0.04, 0.02],
        "population_growth": [0.02, 0.01, 0.00],
        "income_growth": [0.05, 0.04, 0.03],
        "rental_vacancy_rate": [0.04, 0.06, 0.08],
        "rent_growth": [0.04, 0.02, 0.00],
    })


# --- Percentile scores -------------------------------------------------------------

def test_percentile_higher_is_better():
    scores = scoring.percentile_score(pd.Series([10, 30, 20]), higher_is_better=True)
    assert list(scores) == [0, 100, 50]


def test_percentile_lower_is_better_flips_direction():
    scores = scoring.percentile_score(pd.Series([10, 30, 20]), higher_is_better=False)
    assert list(scores) == [100, 0, 50]


def test_percentile_ties_share_a_score():
    scores = scoring.percentile_score(pd.Series([1, 1, 2]))
    assert scores[0] == scores[1] == 25
    assert scores[2] == 100


def test_percentile_ignores_missing_values():
    scores = scoring.percentile_score(pd.Series([1, np.nan, 2]))
    assert scores[0] == 0 and scores[2] == 100
    assert np.isnan(scores[1])


def test_percentile_single_market_is_neutral():
    assert list(scoring.percentile_score(pd.Series([5.0]))) == [50]


def test_percentile_is_robust_to_outliers():
    # A huge outlier would squash min-max scores; percentile ranks are unaffected.
    normal = scoring.percentile_score(pd.Series([1, 2, 3, 4]))
    with_outlier = scoring.percentile_score(pd.Series([1, 2, 3, 1_000]))
    assert list(normal) == list(with_outlier)


# --- Weights ------------------------------------------------------------------------

@pytest.mark.parametrize("preset", list(config.WEIGHT_PRESETS))
def test_presets_sum_to_100_percent(preset):
    scoring.validate_weights(config.WEIGHT_PRESETS[preset])


@pytest.mark.parametrize(
    "weights",
    [
        {"affordability": 0.5, "growth": 0.3, "rental_demand": 0.3},  # 110%
        {"affordability": 0.3, "growth": 0.3, "rental_demand": 0.3},  # 90%
        {"affordability": 1.2, "growth": -0.2, "rental_demand": 0.0},  # negative
        {"affordability": 0.5, "growth": 0.5},  # missing a pillar
    ],
)
def test_bad_weights_are_rejected(weights):
    with pytest.raises(ValueError):
        scoring.validate_weights(weights)


# --- Composite score -------------------------------------------------------------------

def test_best_market_ranks_first_with_score_100():
    scored = scoring.score_markets(make_markets(), BALANCED)
    assert list(scored["metro"]) == ["A", "B", "C"]
    assert list(scored["rank"]) == [1, 2, 3]
    assert scored["composite_score"].tolist() == pytest.approx([100, 50, 0])


def test_composite_is_weighted_sum_of_pillars():
    markets = make_markets()
    markets["rent_growth"] = [0.00, 0.02, 0.04]  # flip one metric so pillars disagree
    scored = scoring.score_markets(markets, BALANCED).set_index("metro")
    a = scored.loc["A"]
    assert a["rental_demand_score"] == pytest.approx((100 + 0) / 2)
    expected = 0.4 * a["affordability_score"] + 0.3 * a["growth_score"] + 0.3 * a["rental_demand_score"]
    assert a["composite_score"] == pytest.approx(expected)


def test_weights_change_the_ranking():
    # X is cheap but not growing; Y is pricey but growing fast.
    markets = pd.DataFrame({
        "metro": ["X", "Y"],
        "rent_to_price": [0.007, 0.004], "price_to_income": [3.0, 6.0], "effective_tax_rate": [0.01, 0.02],
        "home_price_growth": [0.01, 0.07], "population_growth": [0.00, 0.02], "income_growth": [0.02, 0.06],
        "rental_vacancy_rate": [0.06, 0.06], "rent_growth": [0.02, 0.02],
    })
    cash = scoring.score_markets(markets, config.WEIGHT_PRESETS["Cash-flow focused"])
    growth = scoring.score_markets(markets, config.WEIGHT_PRESETS["Growth focused"])
    assert cash["metro"].iloc[0] == "X"
    assert growth["metro"].iloc[0] == "Y"


# --- Missing data ----------------------------------------------------------------------

def test_missing_metric_uses_rest_of_pillar_and_flags_market():
    markets = make_markets()
    markets.loc[0, "income_growth"] = np.nan
    scored = scoring.score_markets(markets, BALANCED).set_index("metro")
    a = scored.loc["A"]
    assert a["growth_score"] == pytest.approx(100)  # from home price and population growth only
    assert a["has_missing_data"]
    assert "income growth" in a["missing_metrics"].lower()
    assert not scored.loc["B", "has_missing_data"]


def test_missing_whole_pillar_reweights_remaining_pillars():
    markets = make_markets()
    markets.loc[1, ["rental_vacancy_rate", "rent_growth"]] = np.nan
    scored = scoring.score_markets(markets, BALANCED).set_index("metro")
    b = scored.loc["B"]
    assert np.isnan(b["rental_demand_score"])
    expected = (0.4 * b["affordability_score"] + 0.3 * b["growth_score"]) / 0.7
    assert b["composite_score"] == pytest.approx(expected)


def test_demo_dataset_with_gaps_scores_without_crashing():
    demo = pd.read_csv(config.DEMO_DATA_PATH)
    scored = scoring.score_markets(demo, BALANCED)
    assert scored["composite_score"].notna().all()
    assert scored["has_missing_data"].sum() == 1


# --- Rank sensitivity ------------------------------------------------------------------

def test_rank_sensitivity_table():
    table = scoring.rank_sensitivity(make_markets())
    assert list(table.columns) == ["metro", *config.WEIGHT_PRESETS, "Rank range"]
    # A is best on everything, so its rank never moves.
    assert table.set_index("metro").loc["A", "Rank range"] == 0
