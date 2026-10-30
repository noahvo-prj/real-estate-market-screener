"""Tests for src/data_loader.py. Run with: pytest"""

import numpy as np
import pandas as pd
import pytest

import config
from src import data_loader


@pytest.fixture
def real_markets() -> pd.DataFrame:
    return pd.read_csv(data_loader.ROOT / config.PROCESSED_DATA_PATH)


def test_loads_real_dataset_when_valid():
    markets, is_demo = data_loader.load_markets()
    assert not is_demo
    assert len(markets) == len(config.METROS)


def test_falls_back_to_demo_when_file_missing(tmp_path):
    markets, is_demo = data_loader.load_markets(path=tmp_path / "missing.csv")
    assert is_demo
    assert (markets["data_source"] == "demo").all()


def test_falls_back_to_demo_when_file_empty(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    assert data_loader.load_markets(path=empty)[1]


def test_falls_back_to_demo_when_columns_missing(tmp_path, real_markets):
    broken = tmp_path / "broken.csv"
    real_markets.drop(columns=["rent_growth"]).to_csv(broken, index=False)
    assert data_loader.load_markets(path=broken)[1]


def test_falls_back_to_demo_when_metros_duplicated(tmp_path, real_markets):
    dupes = tmp_path / "dupes.csv"
    pd.concat([real_markets, real_markets.head(1)]).to_csv(dupes, index=False)
    assert data_loader.load_markets(path=dupes)[1]


def test_text_in_number_column_becomes_missing(tmp_path, real_markets):
    typo = tmp_path / "typo.csv"
    real_markets["rent_to_price"] = real_markets["rent_to_price"].astype(object)
    real_markets.loc[2, "rent_to_price"] = "abc"
    real_markets.to_csv(typo, index=False)

    markets, is_demo = data_loader.load_markets(path=typo)
    assert not is_demo
    assert np.isnan(markets.loc[2, "rent_to_price"])
    assert pd.api.types.is_float_dtype(markets["rent_to_price"])


def test_data_version_changes_when_file_changes(tmp_path, real_markets):
    path = tmp_path / "markets.csv"
    assert data_loader.data_version(path=path)[0] == 0.0  # missing file
    real_markets.to_csv(path, index=False)
    assert data_loader.data_version(path=path)[0] > 0
