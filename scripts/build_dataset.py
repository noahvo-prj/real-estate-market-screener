"""Build data/processed/markets.csv from Zillow files and Census data.

Usage (from the project folder):
    python scripts/build_dataset.py            # build the real dataset
    python scripts/build_dataset.py --refresh  # re-download Census data first
    python scripts/build_dataset.py --demo     # rebuild the labeled demo dataset

Inputs:
    data/raw/zillow_zhvi_metro.csv   ZHVI, all homes, smoothed, seasonally adjusted (manual download)
    data/raw/zillow_zori_metro.csv   ZORI, all homes plus multifamily, smoothed (manual download)
    Census ACS 1-year API            needs CENSUS_API_KEY in .env; cached to data/raw/
    Census Population Estimates      CSV file from census.gov; cached to data/raw/

Missing values stay missing (NaN). Nothing is filled in or estimated.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

RAW = ROOT / "data" / "raw"
CENSUS_GEO = "metropolitan statistical area/micropolitan statistical area"

# Census variable codes -> our column names
ACS_DETAIL_VARS = {
    "B19013_001E": "median_household_income",
    "B25077_001E": "median_home_value_acs",
    "B25103_001E": "median_real_estate_taxes",
}
ACS_PROFILE_VARS = {"DP04_0005E": "rental_vacancy_rate"}
PEP_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/"
    f"2020-{config.PEP_VINTAGE}/metro/totals/cbsa-est{config.PEP_VINTAGE}-alldata.csv"
)


def annualized_growth(start: pd.Series, end: pd.Series, years: float) -> pd.Series:
    """Compound annual growth rate: (end / start)^(1 / years) - 1."""
    ratio = end / start.where(start > 0)
    return ratio ** (1 / years) - 1


# --- Zillow ---------------------------------------------------------------------

def load_zillow(path: Path, value_name: str, growth_years: int) -> pd.DataFrame:
    """Latest value and annualized growth over `growth_years` for each metro in config."""
    df = pd.read_csv(path)
    date_cols = [c for c in df.columns if c[:4].isdigit()]
    latest_col = date_cols[-1]
    start_col = date_cols[-1 - 12 * growth_years]

    names = [m["zillow_name"] for m in config.METROS]
    df = df[df["RegionName"].isin(names)].set_index("RegionName")
    out = pd.DataFrame(index=df.index)
    out[value_name] = df[latest_col]
    out[f"{value_name}_growth"] = annualized_growth(df[start_col], df[latest_col], growth_years)
    out[f"{value_name}_month"] = latest_col[:7]
    return out


# --- Census ---------------------------------------------------------------------

def fetch_acs(year: int, variables: list[str], profile: bool, api_key: str, refresh: bool) -> pd.DataFrame:
    """All metros for the given ACS 1-year variables. Cached as JSON in data/raw/."""
    table = "profile" if profile else "detail"
    cache = RAW / f"census_acs1_{year}_{table}.json"
    if refresh or not cache.exists():
        url = f"https://api.census.gov/data/{year}/acs/acs1" + ("/profile" if profile else "")
        params = {"get": ",".join(["NAME"] + variables), "for": f"{CENSUS_GEO}:*", "key": api_key}
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        cache.write_text(response.text)

    rows = json.loads(cache.read_text())
    df = pd.DataFrame(rows[1:], columns=rows[0]).rename(columns={CENSUS_GEO: "cbsa_code"})
    df["cbsa_code"] = df["cbsa_code"].astype(int)
    for var in variables:
        df[var] = pd.to_numeric(df[var], errors="coerce")
        df.loc[df[var] < 0, var] = np.nan  # Census uses large negative numbers for "not available"
    return df.set_index("cbsa_code")


def fetch_population(refresh: bool) -> pd.DataFrame:
    """Metro population estimates for each July. Cached as CSV in data/raw/."""
    cache = RAW / f"census_pep_cbsa_v{config.PEP_VINTAGE}.csv"
    if refresh or not cache.exists():
        response = requests.get(PEP_URL, timeout=120)
        response.raise_for_status()
        cache.write_bytes(response.content)

    df = pd.read_csv(cache, encoding="latin-1")
    df = df[df["LSAD"] == "Metropolitan Statistical Area"]
    return df.set_index("CBSA")


# --- Assemble -------------------------------------------------------------------

def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Scoring metrics computed from the raw columns. Shared by the real and demo datasets."""
    df["rent_to_price"] = df["zori"] / df["zhvi"]
    df["price_to_income"] = df["zhvi"] / df["median_household_income"]
    df["effective_tax_rate"] = df["median_real_estate_taxes"] / df["median_home_value_acs"]
    return df


def build_markets(api_key: str, refresh: bool) -> pd.DataFrame:
    metros = pd.DataFrame(config.METROS)
    if "cbsa_code_base_year" not in metros:
        metros["cbsa_code_base_year"] = np.nan
    metros["cbsa_code_base_year"] = metros["cbsa_code_base_year"].fillna(metros["cbsa_code"]).astype(int)

    zhvi = load_zillow(RAW / "zillow_zhvi_metro.csv", "zhvi", config.HOME_PRICE_GROWTH_YEARS)
    zori = load_zillow(RAW / "zillow_zori_metro.csv", "zori", config.RENT_GROWTH_YEARS)

    detail_vars = list(ACS_DETAIL_VARS)
    acs = fetch_acs(config.ACS_YEAR, detail_vars, profile=False, api_key=api_key, refresh=refresh)
    profile = fetch_acs(config.ACS_YEAR, list(ACS_PROFILE_VARS), profile=True, api_key=api_key, refresh=refresh)
    acs_base = fetch_acs(config.ACS_BASE_YEAR, ["B19013_001E"], profile=False, api_key=api_key, refresh=refresh)
    pep = fetch_population(refresh)

    df = metros.set_index("zillow_name").join(zhvi).join(zori).reset_index(names="metro")
    df["census_name"] = df["cbsa_code"].map(acs["NAME"])
    for var, column in ACS_DETAIL_VARS.items():
        df[column] = df["cbsa_code"].map(acs[var])
    df["rental_vacancy_rate"] = df["cbsa_code"].map(profile["DP04_0005E"]) / 100

    income_base = df["cbsa_code_base_year"].map(acs_base["B19013_001E"])
    income_years = config.ACS_YEAR - config.ACS_BASE_YEAR
    df["income_growth"] = annualized_growth(income_base, df["median_household_income"], income_years)

    pop_start = df["cbsa_code"].map(pep[f"POPESTIMATE{config.PEP_BASE_YEAR}"])
    df["population"] = df["cbsa_code"].map(pep[f"POPESTIMATE{config.PEP_VINTAGE}"])
    pop_years = config.PEP_VINTAGE - config.PEP_BASE_YEAR
    df["population_growth"] = annualized_growth(pop_start, df["population"], pop_years)

    df = add_derived_metrics(df)
    df = df.rename(columns={"zhvi_growth": "home_price_growth", "zori_growth": "rent_growth"})
    df["acs_year"] = config.ACS_YEAR
    df["data_source"] = "real"
    return df[OUTPUT_COLUMNS]


OUTPUT_COLUMNS = [
    "metro", "cbsa_code", "census_name",
    "zhvi", "zori", "zhvi_month",
    "median_household_income", "median_home_value_acs", "median_real_estate_taxes", "population",
    "rent_to_price", "price_to_income", "effective_tax_rate",
    "home_price_growth", "population_growth", "income_growth",
    "rental_vacancy_rate", "rent_growth",
    "acs_year", "data_source",
]


# --- Demo dataset -----------------------------------------------------------------

def build_demo() -> pd.DataFrame:
    """Fictional markets with made-up but realistic-looking numbers, for when real data is missing.

    Names are fictional on purpose so demo numbers can never be mistaken for a real metro.
    """
    rows = [
        # metro,                  zhvi,    zori, income,  value,   taxes, pop,       hpg,   popg,   incg,  vac,   rentg
        ("Demo City A (sample)", 610_000, 2_900, 105_000, 640_000, 6_100, 3_100_000, 0.045, 0.004, 0.050, 0.045, 0.020),
        ("Demo City B (sample)", 480_000, 2_300, 92_000, 500_000, 4_400, 2_400_000, 0.060, 0.012, 0.055, 0.060, 0.030),
        ("Demo City C (sample)", 395_000, 2_050, 84_000, 410_000, 6_900, 1_800_000, 0.055, 0.018, 0.048, 0.075, 0.025),
        ("Demo City D (sample)", 330_000, 1_850, 78_000, 345_000, 3_000, 2_100_000, 0.050, 0.015, 0.045, 0.080, 0.018),
        ("Demo City E (sample)", 285_000, 1_650, 74_000, 300_000, 4_300, 1_200_000, 0.062, 0.006, 0.052, 0.055, 0.035),
        ("Demo City F (sample)", 245_000, 1_500, 70_000, 255_000, 3_400, 2_300_000, 0.058, 0.002, 0.040, 0.065, 0.032),
        ("Demo City G (sample)", 220_000, 1_400, 66_000, 230_000, 2_500, 1_500_000, 0.048, 0.009, 0.042, 0.090, 0.015),
        ("Demo City H (sample)", 205_000, 1_350, 64_000, 215_000, 3_700, 1_100_000, 0.065, -0.002, 0.038, 0.070, 0.040),
        ("Demo City I (sample)", 190_000, 1_300, 60_000, 200_000, 2_100, 1_300_000, 0.040, 0.001, 0.035, 0.105, 0.010),
        ("Demo City J (sample)", 260_000, None,  72_000, 270_000, 3_100, 900_000,   0.052, 0.011, None,  0.060, None),
    ]
    columns = [
        "metro", "zhvi", "zori", "median_household_income", "median_home_value_acs",
        "median_real_estate_taxes", "population", "home_price_growth", "population_growth",
        "income_growth", "rental_vacancy_rate", "rent_growth",
    ]
    df = pd.DataFrame(rows, columns=columns).astype({"zori": float, "income_growth": float, "rent_growth": float})
    df = add_derived_metrics(df)
    df["cbsa_code"] = pd.NA
    df["census_name"] = "DEMO DATA - not a real metro"
    df["zhvi_month"] = "demo"
    df["acs_year"] = pd.NA
    df["data_source"] = "demo"
    return df[OUTPUT_COLUMNS]


# --- Main ---------------------------------------------------------------------------

def report_missing(df: pd.DataFrame) -> None:
    missing = df.set_index("metro").isna()
    problems = {metro: list(row[row].index) for metro, row in missing.iterrows() if row.any()}
    if problems:
        print("Missing values (left blank, flagged in the app):")
        for metro, cols in problems.items():
            print(f"  {metro}: {', '.join(cols)}")
    else:
        print("No missing values.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="re-download Census data")
    parser.add_argument("--demo", action="store_true", help="rebuild the demo dataset only")
    args = parser.parse_args()

    if args.demo:
        out_path = ROOT / config.DEMO_DATA_PATH
        build_demo().to_csv(out_path, index=False)
        print(f"Wrote demo dataset to {out_path.relative_to(ROOT)}")
        return

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("CENSUS_API_KEY")
    if not api_key:
        sys.exit("CENSUS_API_KEY is missing. Add it to .env (see README).")

    markets = build_markets(api_key, refresh=args.refresh)
    out_path = ROOT / config.PROCESSED_DATA_PATH
    markets.to_csv(out_path, index=False)
    print(f"Wrote {len(markets)} markets to {out_path.relative_to(ROOT)}")
    report_missing(markets)


if __name__ == "__main__":
    main()
