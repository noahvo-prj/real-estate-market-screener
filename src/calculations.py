"""Finance calculations for the property calculator.

Pure Python and pandas only: no Streamlit, so every function can be unit tested.
Percentages are decimals (0.07 = 7%). Money is in dollars. Functions return None
for ratios that are undefined (for example, anything divided by zero).
"""

from dataclasses import dataclass, replace

import pandas as pd

import config

MONTHS_PER_YEAR = 12
DAYS_PER_MONTH = 365 / 12

_D = config.CALCULATOR_DEFAULTS


@dataclass
class PropertyInputs:
    """Everything the calculator needs to evaluate one property."""

    # Property
    purchase_price: float
    rent_per_unit: float  # monthly rent for one rentable unit
    property_tax_rate: float  # annual taxes / purchase price
    comparable_rent: float = 0.0  # monthly rent for a similar unit, for rent-vs-own
    units: int = _D["units"]
    owner_units: int = _D["owner_units"]

    # Financing
    down_payment: float = 0.0
    interest_rate: float = _D["interest_rate"]
    loan_term_years: int = _D["loan_term_years"]
    use_va_loan: bool = _D["use_va_loan"]
    va_first_use: bool = _D["va_first_use"]
    va_fee_exempt: bool = _D["va_fee_exempt"]
    finance_funding_fee: bool = _D["finance_funding_fee"]
    closing_costs: float = 0.0

    # Operating costs
    insurance_annual: float = _D["insurance_annual"]
    hoa_monthly: float = _D["hoa_monthly"]
    vacancy_rate: float = _D["vacancy_rate"]
    maintenance_rate: float = _D["maintenance_rate"]  # share of full-property rent
    capex_rate: float = _D["capex_rate"]  # share of full-property rent
    management_rate: float = _D["management_rate"]  # share of rent collected
    owner_utilities_monthly: float = _D["owner_utilities_monthly"]
    other_monthly: float = _D["other_monthly"]

    # Upfront cash
    reserves: float = _D["reserves"]
    initial_repairs: float = _D["initial_repairs"]
    furnishing: float = _D["furnishing"]


def validate_inputs(inputs: PropertyInputs) -> list[str]:
    """Return a list of plain-English problems with the inputs (empty if valid)."""
    errors = []
    if inputs.purchase_price <= 0:
        errors.append("Purchase price must be greater than zero.")
    if inputs.down_payment < 0 or inputs.down_payment > inputs.purchase_price:
        errors.append("Down payment must be between $0 and the purchase price.")
    if not 2 <= inputs.units <= 4:
        errors.append("Number of units must be between 2 and 4.")
    if not 0 <= inputs.owner_units < inputs.units:
        errors.append("Owner-occupied units must be fewer than total units.")
    if inputs.loan_term_years <= 0:
        errors.append("Loan term must be at least 1 year.")

    dollar_fields = [
        "rent_per_unit", "comparable_rent", "closing_costs", "insurance_annual",
        "hoa_monthly", "owner_utilities_monthly", "other_monthly", "reserves",
        "initial_repairs", "furnishing",
    ]
    for name in dollar_fields:
        if getattr(inputs, name) < 0:
            errors.append(f"{_label(name)} cannot be negative.")

    rate_fields = [
        "interest_rate", "property_tax_rate", "vacancy_rate", "maintenance_rate",
        "capex_rate", "management_rate",
    ]
    for name in rate_fields:
        if not 0 <= getattr(inputs, name) <= 1:
            errors.append(f"{_label(name)} must be between 0% and 100%.")
    return errors


def _label(field_name: str) -> str:
    return field_name.replace("_", " ").capitalize()


def safe_divide(numerator: float, denominator: float) -> float | None:
    """Divide, returning None instead of crashing when the denominator is zero."""
    if denominator == 0:
        return None
    return numerator / denominator


# --- Loan math ----------------------------------------------------------------

def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    """Monthly principal and interest on a fixed-rate, fully amortizing loan.

    M = P * r(1+r)^n / ((1+r)^n - 1), with r = annual rate / 12 and n = years * 12.
    At 0% interest the payment is simply P / n.
    """
    if principal <= 0:
        return 0.0
    n = years * MONTHS_PER_YEAR
    r = annual_rate / MONTHS_PER_YEAR
    if r == 0:
        return principal / n
    growth = (1 + r) ** n
    return principal * r * growth / (growth - 1)


def remaining_balance(principal: float, annual_rate: float, years: int, months_paid: int) -> float:
    """Loan balance left after a number of monthly payments."""
    n = years * MONTHS_PER_YEAR
    if principal <= 0 or months_paid >= n:
        return 0.0
    r = annual_rate / MONTHS_PER_YEAR
    if r == 0:
        return principal * (1 - months_paid / n)
    payment = monthly_payment(principal, annual_rate, years)
    growth = (1 + r) ** months_paid
    return principal * growth - payment * (growth - 1) / r


def va_funding_fee_rate(down_payment_pct: float, first_use: bool = True, exempt: bool = False) -> float:
    """VA funding fee rate for a purchase loan, from the table in config.py."""
    if exempt:
        return 0.0
    tiers = config.VA_FUNDING_FEE_RATES["first_use" if first_use else "subsequent_use"]
    for min_down, rate in tiers:
        if down_payment_pct >= min_down:
            return rate
    return tiers[-1][1]


def funding_fee(inputs: PropertyInputs) -> float:
    """VA funding fee in dollars (0 if not a VA loan or if exempt)."""
    if not inputs.use_va_loan:
        return 0.0
    base_loan = max(inputs.purchase_price - inputs.down_payment, 0.0)
    down_pct = safe_divide(inputs.down_payment, inputs.purchase_price) or 0.0
    rate = va_funding_fee_rate(down_pct, inputs.va_first_use, inputs.va_fee_exempt)
    return base_loan * rate


def loan_amount(inputs: PropertyInputs) -> float:
    """Price minus down payment, plus the funding fee if it is financed."""
    base_loan = max(inputs.purchase_price - inputs.down_payment, 0.0)
    if inputs.finance_funding_fee:
        return base_loan + funding_fee(inputs)
    return base_loan


def property_monthly_payment(inputs: PropertyInputs) -> float:
    """Monthly principal and interest for this property's loan."""
    return monthly_payment(loan_amount(inputs), inputs.interest_rate, inputs.loan_term_years)


def cash_needed_breakdown(inputs: PropertyInputs) -> dict[str, float]:
    """Itemized cash needed at purchase. Shows that 0% down is not $0 invested."""
    fee_paid_in_cash = 0.0 if inputs.finance_funding_fee else funding_fee(inputs)
    items = {
        "Down payment": inputs.down_payment,
        "Closing costs": inputs.closing_costs,
        "VA funding fee (paid in cash)": fee_paid_in_cash,
        "Reserves": inputs.reserves,
        "Initial repairs": inputs.initial_repairs,
        "Furnishing": inputs.furnishing,
    }
    items["Total"] = sum(items.values())
    return items


# --- Operations -----------------------------------------------------------------

def annual_operations(
    inputs: PropertyInputs,
    rented_units: int,
    rent_factor: float = 1.0,
    expense_factor: float = 1.0,
) -> dict[str, float]:
    """Annual rent and operating expenses when `rented_units` units are rented out.

    Maintenance and capex are a share of the whole building's potential rent, because
    the building wears out whether or not the owner lives in a unit. Management is a
    share of rent actually collected. Operating expenses never include the mortgage.
    `rent_factor` and `expense_factor` scale rents and fixed costs for projections.
    """
    rent = inputs.rent_per_unit * rent_factor
    gpr = rent * rented_units * MONTHS_PER_YEAR
    effective_income = gpr * (1 - inputs.vacancy_rate)
    full_property_rent = rent * inputs.units * MONTHS_PER_YEAR

    expenses = {
        "Property taxes": inputs.purchase_price * inputs.property_tax_rate * expense_factor,
        "Insurance": inputs.insurance_annual * expense_factor,
        "HOA": inputs.hoa_monthly * MONTHS_PER_YEAR * expense_factor,
        "Maintenance": full_property_rent * inputs.maintenance_rate,
        "Capex reserve": full_property_rent * inputs.capex_rate,
        "Management": effective_income * inputs.management_rate,
        "Owner-paid utilities": inputs.owner_utilities_monthly * MONTHS_PER_YEAR * expense_factor,
        "Other": inputs.other_monthly * MONTHS_PER_YEAR * expense_factor,
    }
    return {
        "gross_potential_rent": gpr,
        "effective_income": effective_income,
        "operating_expenses": sum(expenses.values()),
        "expense_breakdown": expenses,
    }


def investor_view(inputs: PropertyInputs) -> dict:
    """Metrics as if every unit, including the owner's, were rented out."""
    ops = annual_operations(inputs, rented_units=inputs.units)
    monthly_pi = property_monthly_payment(inputs)
    annual_debt_service = monthly_pi * MONTHS_PER_YEAR
    noi = ops["effective_income"] - ops["operating_expenses"]
    annual_cash_flow = noi - annual_debt_service
    cash_needed = cash_needed_breakdown(inputs)["Total"]

    return {
        **ops,
        "noi": noi,
        "cap_rate": safe_divide(noi, inputs.purchase_price),
        "monthly_pi": monthly_pi,
        "annual_debt_service": annual_debt_service,
        "monthly_cash_flow": annual_cash_flow / MONTHS_PER_YEAR,
        "annual_cash_flow": annual_cash_flow,
        "dscr": safe_divide(noi, annual_debt_service),
        "break_even_occupancy": safe_divide(
            ops["operating_expenses"] + annual_debt_service, ops["gross_potential_rent"]
        ),
        "cash_on_cash": safe_divide(annual_cash_flow, cash_needed),
    }


def owner_view(inputs: PropertyInputs) -> dict:
    """House-hack metrics: rent comes only from the units the owner doesn't live in."""
    rented_units = inputs.units - inputs.owner_units
    ops = annual_operations(inputs, rented_units=rented_units)
    monthly_pi = property_monthly_payment(inputs)
    monthly_rent = ops["effective_income"] / MONTHS_PER_YEAR
    monthly_expenses = ops["operating_expenses"] / MONTHS_PER_YEAR
    net_housing_cost = monthly_pi + monthly_expenses - monthly_rent

    return {
        **ops,
        "rented_units": rented_units,
        "monthly_pi": monthly_pi,
        "monthly_operating_expenses": monthly_expenses,
        "monthly_effective_rent": monthly_rent,
        "net_housing_cost": net_housing_cost,
        "comparable_rent": inputs.comparable_rent,
        "monthly_savings_vs_renting": inputs.comparable_rent - net_housing_cost,
    }


def str_unit_monthly(
    nightly_rate: float,
    occupancy_rate: float,
    platform_fee_rate: float,
    cleaning_monthly: float,
    extra_costs_monthly: float,
) -> dict[str, float]:
    """Rough monthly numbers for renting one unit short-term. Check local STR rules first."""
    gross = nightly_rate * occupancy_rate * DAYS_PER_MONTH
    platform_fees = gross * platform_fee_rate
    net = gross - platform_fees - cleaning_monthly - extra_costs_monthly
    return {"gross_revenue": gross, "platform_fees": platform_fees, "net_revenue": net}


# --- Projection and sensitivity ---------------------------------------------------

def _rented_units(inputs: PropertyInputs, view: str) -> int:
    if view == "investor":
        return inputs.units
    if view == "owner":
        return inputs.units - inputs.owner_units
    raise ValueError("view must be 'investor' or 'owner'")


def project(
    inputs: PropertyInputs,
    view: str = "owner",
    years: int = config.PROJECTION_DEFAULTS["years"],
    appreciation_rate: float = config.PROJECTION_DEFAULTS["appreciation_rate"],
    rent_growth_rate: float = config.PROJECTION_DEFAULTS["rent_growth_rate"],
    expense_growth_rate: float = config.PROJECTION_DEFAULTS["expense_growth_rate"],
) -> pd.DataFrame:
    """Year-by-year value, loan balance, equity and cash flow. Assumption-driven, not a forecast.

    In the owner view, cash flow is usually negative: it is what the owner pays to live there.
    """
    loan = loan_amount(inputs)
    monthly_pi = property_monthly_payment(inputs)
    term_months = inputs.loan_term_years * MONTHS_PER_YEAR
    rented = _rented_units(inputs, view)

    rows = []
    cumulative = 0.0
    for year in range(1, years + 1):
        growth_years = year - 1
        ops = annual_operations(
            inputs,
            rented_units=rented,
            rent_factor=(1 + rent_growth_rate) ** growth_years,
            expense_factor=(1 + expense_growth_rate) ** growth_years,
        )
        payments_this_year = min(MONTHS_PER_YEAR, max(0, term_months - growth_years * MONTHS_PER_YEAR))
        cash_flow = ops["effective_income"] - ops["operating_expenses"] - monthly_pi * payments_this_year
        cumulative += cash_flow

        value = inputs.purchase_price * (1 + appreciation_rate) ** year
        balance = remaining_balance(loan, inputs.interest_rate, inputs.loan_term_years, year * MONTHS_PER_YEAR)
        rows.append({
            "year": year,
            "property_value": value,
            "loan_balance": balance,
            "equity": value - balance,
            "annual_cash_flow": cash_flow,
            "cumulative_cash_flow": cumulative,
        })
    return pd.DataFrame(rows)


def headline_metric(inputs: PropertyInputs, view: str) -> float:
    """Investor: monthly cash flow. Owner: net monthly housing cost."""
    if view == "investor":
        return investor_view(inputs)["monthly_cash_flow"]
    if view == "owner":
        return owner_view(inputs)["net_housing_cost"]
    raise ValueError("view must be 'investor' or 'owner'")


def _shock(inputs: PropertyInputs, name: str, method: str, size: float, direction: int) -> PropertyInputs:
    value = getattr(inputs, name)
    new_value = value + direction * size if method == "add" else value * (1 + direction * size)
    new_value = max(new_value, 0.0)
    if name.endswith("_rate"):
        new_value = min(new_value, 1.0)
    return replace(inputs, **{name: new_value})


def sensitivity(inputs: PropertyInputs, view: str = "owner") -> pd.DataFrame:
    """How the headline metric moves when each key input is shocked down and up.

    Returns one row per input, sorted with the biggest swing first (tornado order).
    """
    base = headline_metric(inputs, view)
    rows = []
    for name, (label, method, size) in config.SENSITIVITY_SHOCKS.items():
        low = headline_metric(_shock(inputs, name, method, size, -1), view)
        high = headline_metric(_shock(inputs, name, method, size, +1), view)
        rows.append({
            "input": label,
            "base": base,
            "input_down": low,
            "input_up": high,
            "swing": abs(high - low),
        })
    return pd.DataFrame(rows).sort_values("swing", ascending=False, ignore_index=True)
