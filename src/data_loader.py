"""Load and validate the market dataset, falling back to the labeled demo data."""

from pathlib import Path

import pandas as pd

import config

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = ["metro", *config.METRICS]
NUMERIC_COLUMNS = [
    *config.METRICS, "zhvi", "zori", "median_household_income", "median_home_value_acs",
    "median_real_estate_taxes", "population",
]


def validate_markets(df: pd.DataFrame) -> None:
    """Raise ValueError if the dataset can't be used by the app."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing columns: {', '.join(missing)}")
    if df.empty:
        raise ValueError("Dataset has no rows.")
    if df["metro"].duplicated().any():
        raise ValueError("Dataset has duplicate metro names.")


def coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Turn numeric columns into numbers. Anything unreadable becomes missing, like any other gap."""
    df = df.copy()
    for col in NUMERIC_COLUMNS:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _read(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(ROOT / path)
    validate_markets(df)
    return coerce_numeric(df)


def load_markets(
    path: str | Path = config.PROCESSED_DATA_PATH,
    demo_path: str | Path = config.DEMO_DATA_PATH,
) -> tuple[pd.DataFrame, bool]:
    """Return (markets, is_demo). Uses the demo dataset if the real one is missing or invalid."""
    try:
        return _read(path), False
    except (FileNotFoundError, pd.errors.EmptyDataError, ValueError):
        return _read(demo_path), True


def data_version(
    path: str | Path = config.PROCESSED_DATA_PATH,
    demo_path: str | Path = config.DEMO_DATA_PATH,
) -> tuple[float, float]:
    """Last-modified times of the data files. Changes whenever a file is rebuilt, so caches refresh."""
    return tuple(
        (ROOT / p).stat().st_mtime if (ROOT / p).exists() else 0.0 for p in (path, demo_path)
    )
