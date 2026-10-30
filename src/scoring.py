"""Market scoring: percentile ranks -> pillar scores -> weighted composite.

No Streamlit here, so it can be unit tested. Scores are relative to the markets being
compared: an 80 means the market beats 80% of the comparison set on that metric.
"""

import pandas as pd

import config

WEIGHT_TOLERANCE = 1e-6


def percentile_score(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Score each value 0-100 by the share of the other markets it beats.

    The best market gets 100 and the worst gets 0; ties share the average.
    Missing values stay missing and are left out of the comparison.
    A lone market (nothing to compare against) gets a neutral 50.
    """
    ranks = values.rank(ascending=higher_is_better, method="average")
    count = values.notna().sum()
    if count == 1:
        return ranks.where(ranks.isna(), 50.0)
    return (ranks - 1) / (count - 1) * 100


def validate_weights(weights: dict[str, float]) -> None:
    """Raise ValueError unless there is a non-negative weight for every pillar and they sum to 1."""
    if set(weights) != set(config.PILLAR_LABELS):
        raise ValueError(f"Weights must cover exactly these pillars: {', '.join(config.PILLAR_LABELS)}.")
    if any(w < 0 for w in weights.values()):
        raise ValueError("Weights cannot be negative.")
    if abs(sum(weights.values()) - 1) > WEIGHT_TOLERANCE:
        raise ValueError(f"Weights must add up to 100% (they add up to {sum(weights.values()):.0%}).")


def score_markets(markets: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    """Add metric scores, pillar scores, a composite score and a rank to each market.

    Missing data: a pillar is scored from whichever of its metrics are available. If a
    whole pillar is missing, the composite is built from the remaining pillars with their
    weights scaled up to 100%. Either way the market is flagged in `missing_metrics`.
    """
    validate_weights(weights)
    scored = markets.copy()

    for metric, spec in config.METRICS.items():
        scored[f"{metric}_score"] = percentile_score(scored[metric], spec["better"] == "higher")

    for pillar in config.PILLAR_LABELS:
        metric_cols = [f"{m}_score" for m, spec in config.METRICS.items() if spec["pillar"] == pillar]
        scored[f"{pillar}_score"] = scored[metric_cols].mean(axis=1, skipna=True)

    pillar_scores = scored[[f"{p}_score" for p in config.PILLAR_LABELS]]
    pillar_weights = pd.Series({f"{p}_score": w for p, w in weights.items()})
    available_weight = pillar_scores.notna().mul(pillar_weights).sum(axis=1)
    weighted_sum = pillar_scores.mul(pillar_weights).sum(axis=1, skipna=True)
    scored["composite_score"] = (weighted_sum / available_weight).where(available_weight > 0)

    scored["missing_metrics"] = scored[list(config.METRICS)].isna().apply(
        lambda row: ", ".join(config.METRICS[m]["label"] for m in row.index[row]), axis=1
    )
    scored["has_missing_data"] = scored["missing_metrics"] != ""

    scored["rank"] = scored["composite_score"].rank(ascending=False, method="min").astype("Int64")
    return scored.sort_values("rank", ignore_index=True)


def rank_sensitivity(markets: pd.DataFrame, presets: dict[str, dict[str, float]] | None = None) -> pd.DataFrame:
    """Each market's rank under every weight preset, plus how far its rank moves.

    Answers "what could cause the ranking to change?". Sorted by the Balanced rank.
    """
    presets = presets or config.WEIGHT_PRESETS
    table = pd.DataFrame(index=markets["metro"])
    for name, weights in presets.items():
        table[name] = score_markets(markets, weights).set_index("metro")["rank"]
    table["Rank range"] = table.max(axis=1) - table.min(axis=1)
    sort_col = config.DEFAULT_PRESET if config.DEFAULT_PRESET in table else table.columns[0]
    return table.sort_values(sort_col).reset_index()
