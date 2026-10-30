"""Default assumptions and reference tables. Change numbers here, not in the code.

All percentages are stored as decimals (0.07 means 7%).
"""

# --- Markets and data sources ---------------------------------------------------
# 20 metros picked for a mix of price levels and regions. `zillow_name` must match
# Zillow's RegionName; `cbsa_code` is the Census metro code (2023 definitions).
# `cbsa_code_base_year` is only set when the code was different in the base year.
METROS = [
    {"zillow_name": "San Diego, CA", "cbsa_code": 41740},
    {"zillow_name": "Seattle, WA", "cbsa_code": 42660},
    {"zillow_name": "Boston, MA", "cbsa_code": 14460},
    {"zillow_name": "Denver, CO", "cbsa_code": 19740},
    {"zillow_name": "Minneapolis, MN", "cbsa_code": 33460},
    {"zillow_name": "Phoenix, AZ", "cbsa_code": 38060},
    {"zillow_name": "Nashville, TN", "cbsa_code": 34980},
    {"zillow_name": "Raleigh, NC", "cbsa_code": 39580},
    {"zillow_name": "Dallas, TX", "cbsa_code": 19100},
    {"zillow_name": "Atlanta, GA", "cbsa_code": 12060},
    {"zillow_name": "Charlotte, NC", "cbsa_code": 16740},
    {"zillow_name": "Tampa, FL", "cbsa_code": 45300},
    {"zillow_name": "Columbus, OH", "cbsa_code": 18140},
    {"zillow_name": "Houston, TX", "cbsa_code": 26420},
    {"zillow_name": "Kansas City, MO", "cbsa_code": 28140},
    {"zillow_name": "Indianapolis, IN", "cbsa_code": 26900},
    {"zillow_name": "San Antonio, TX", "cbsa_code": 41700},
    {"zillow_name": "Pittsburgh, PA", "cbsa_code": 38300},
    {"zillow_name": "Memphis, TN", "cbsa_code": 32820},
    {"zillow_name": "Cleveland, OH", "cbsa_code": 17410, "cbsa_code_base_year": 17460},
]

ACS_YEAR = 2024  # latest ACS 1-year release available from the Census API
ACS_BASE_YEAR = 2019  # 5 years earlier, for income growth (2020 1-year was not released)
PEP_VINTAGE = 2025  # Census Population Estimates vintage
PEP_BASE_YEAR = 2020
HOME_PRICE_GROWTH_YEARS = 5
RENT_GROWTH_YEARS = 3

PROCESSED_DATA_PATH = "data/processed/markets.csv"
DEMO_DATA_PATH = "data/demo/markets_demo.csv"

# --- Market scoring -------------------------------------------------------------
# Each metric belongs to exactly one pillar. "higher" means a higher value is better.
METRICS = {
    "rent_to_price": {"pillar": "affordability", "better": "higher", "label": "Rent-to-price ratio"},
    "price_to_income": {"pillar": "affordability", "better": "lower", "label": "Price-to-income ratio"},
    "effective_tax_rate": {"pillar": "affordability", "better": "lower", "label": "Effective property tax rate"},
    "home_price_growth": {"pillar": "growth", "better": "higher", "label": "Home price growth (5-yr annualized)"},
    "population_growth": {"pillar": "growth", "better": "higher", "label": "Population growth (5-yr annualized)"},
    "income_growth": {"pillar": "growth", "better": "higher", "label": "Household income growth (5-yr annualized)"},
    "rental_vacancy_rate": {"pillar": "rental_demand", "better": "lower", "label": "Rental vacancy rate"},
    "rent_growth": {"pillar": "rental_demand", "better": "higher", "label": "Rent growth (3-yr annualized)"},
}

PILLAR_LABELS = {
    "affordability": "Affordability / cash flow",
    "growth": "Growth",
    "rental_demand": "Rental demand",
}

WEIGHT_PRESETS = {
    "Cash-flow focused": {"affordability": 0.60, "growth": 0.20, "rental_demand": 0.20},
    "Balanced": {"affordability": 0.40, "growth": 0.30, "rental_demand": 0.30},
    "Growth focused": {"affordability": 0.20, "growth": 0.50, "rental_demand": 0.30},
}
DEFAULT_PRESET = "Balanced"

# --- VA funding fee -----------------------------------------------------------
# Purchase and construction loans. Each tier is (minimum down payment, fee rate),
# checked from the highest down payment to the lowest.
VA_FUNDING_FEE_RATES = {
    "first_use": [(0.10, 0.0125), (0.05, 0.015), (0.0, 0.0215)],
    "subsequent_use": [(0.10, 0.0125), (0.05, 0.015), (0.0, 0.033)],
}
VA_FUNDING_FEE_SOURCE = (
    "VA.gov, 'VA funding fee and closing costs': rates effective April 7, 2023 "
    "(page last updated October 5, 2026; checked October 28, 2026). "
    "https://www.va.gov/housing-assistance/home-loans/funding-fee-and-closing-costs/"
)

# --- Property calculator defaults ---------------------------------------------
# Starting assumptions only. Every one is editable in the app. The interest rate
# is a placeholder: replace it with a real lender quote.
CALCULATOR_DEFAULTS = {
    "units": 2,
    "owner_units": 1,
    "use_va_loan": True,
    "interest_rate": 0.065,
    "loan_term_years": 30,
    "va_first_use": True,
    "va_fee_exempt": False,
    "finance_funding_fee": True,
    "closing_cost_rate": 0.03,  # used by the app to prefill closing costs as % of price
    "insurance_annual": 2400.0,
    "hoa_monthly": 0.0,
    "vacancy_rate": 0.05,
    "maintenance_rate": 0.05,
    "capex_rate": 0.05,
    "management_rate": 0.0,  # 0% when self-managed
    "owner_utilities_monthly": 150.0,
    "other_monthly": 0.0,
    "reserves": 0.0,
    "initial_repairs": 0.0,
    "furnishing": 0.0,
}

PROJECTION_DEFAULTS = {
    "years": 10,
    "appreciation_rate": 0.03,
    "rent_growth_rate": 0.03,
    "expense_growth_rate": 0.03,
}

# --- Sensitivity (tornado) chart ----------------------------------------------
# input name -> (label, how to shock it, size of shock)
#   "add":      move the value up/down by the amount (0.01 = 1 percentage point)
#   "multiply": move the value up/down by that fraction (0.10 = 10%)
SENSITIVITY_SHOCKS = {
    "interest_rate": ("Interest rate (±1 pt)", "add", 0.01),
    "rent_per_unit": ("Rent (±10%)", "multiply", 0.10),
    "vacancy_rate": ("Vacancy (±5 pts)", "add", 0.05),
    "property_tax_rate": ("Property taxes (±25%)", "multiply", 0.25),
    "insurance_annual": ("Insurance (±25%)", "multiply", 0.25),
    "maintenance_rate": ("Maintenance (±2 pts)", "add", 0.02),
}
