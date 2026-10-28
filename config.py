"""Default assumptions and reference tables. Change numbers here, not in the code.

All percentages are stored as decimals (0.07 means 7%).
"""

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
