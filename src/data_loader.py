"""Load and validate the market dataset, falling back to the labeled demo data."""

from pathlib import Path

import pandas as pd

import config

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = ["metro", *config.METRICS]


def validate_markets(df: pd.DataFrame) -> None:
    """Raise ValueError if the dataset can't be used by the app."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing columns: {', '.join(missing)}")
    if df.empty:
        raise ValueError("Dataset has no rows.")
    if df["metro"].duplicated().any():
        raise ValueError("Dataset has duplicate metro names.")


def load_markets(
    path: str | Path = config.PROCESSED_DATA_PATH,
    demo_path: str | Path = config.DEMO_DATA_PATH,
) -> tuple[pd.DataFrame, bool]:
    """Return (markets, is_demo). Uses the demo dataset if the real one is missing or invalid."""
    try:
        markets = pd.read_csv(ROOT / path)
        validate_markets(markets)
        return markets, False
    except (FileNotFoundError, pd.errors.EmptyDataError, ValueError):
        demo = pd.read_csv(ROOT / demo_path)
        validate_markets(demo)
        return demo, True
