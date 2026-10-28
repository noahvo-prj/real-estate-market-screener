"""Tests for src/calculations.py. Run with: pytest"""

import pytest

from src import calculations as calc
from src.calculations import PropertyInputs


def make_inputs(**overrides) -> PropertyInputs:
    """A simple duplex with round numbers, so expected values can be worked out by hand.

    $300k, 2 units at $1,500, 0% down, VA fee exempt, 6% for 30 years, 1% taxes,
    $1,200 insurance, 5% vacancy, 5% maintenance, 5% capex, $100/month utilities.
    """
    values = dict(
        purchase_price=300_000, rent_per_unit=1_500, property_tax_rate=0.01,
        comparable_rent=1_600, units=2, owner_units=1,
        down_payment=0, interest_rate=0.06, loan_term_years=30,
        use_va_loan=True, va_first_use=True, va_fee_exempt=True, finance_funding_fee=True,
        closing_costs=9_000, insurance_annual=1_200, hoa_monthly=0, vacancy_rate=0.05,
        maintenance_rate=0.05, capex_rate=0.05, management_rate=0.0,
        owner_utilities_monthly=100, other_monthly=0,
        reserves=6_000, initial_repairs=0, furnishing=0,
    )
    values.update(overrides)
    return PropertyInputs(**values)


# --- Mortgage math ---------------------------------------------------------------

def test_monthly_payment_matches_known_value():
    # $200,000 at 6% for 30 years is a textbook $1,199.10/month.
    assert calc.monthly_payment(200_000, 0.06, 30) == pytest.approx(1_199.10, abs=0.01)


def test_monthly_payment_at_zero_interest_is_principal_over_months():
    assert calc.monthly_payment(120_000, 0.0, 10) == pytest.approx(1_000.0)


def test_monthly_payment_with_no_loan_is_zero():
    assert calc.monthly_payment(0, 0.06, 30) == 0.0


def test_remaining_balance_start_middle_end():
    assert calc.remaining_balance(200_000, 0.06, 30, 0) == pytest.approx(200_000)
    assert calc.remaining_balance(200_000, 0.06, 30, 360) == 0.0
    assert calc.remaining_balance(120_000, 0.0, 10, 60) == pytest.approx(60_000)
    # Early payments are mostly interest, so after 15 of 30 years well over half is still owed.
    assert calc.remaining_balance(200_000, 0.06, 30, 180) > 100_000


# --- VA funding fee -----------------------------------------------------------------

@pytest.mark.parametrize(
    "down_pct, first_use, expected",
    [
        (0.00, True, 0.0215),
        (0.049, True, 0.0215),
        (0.05, True, 0.015),
        (0.10, True, 0.0125),
        (0.00, False, 0.033),
        (0.05, False, 0.015),
        (0.20, False, 0.0125),
    ],
)
def test_va_funding_fee_rate_tiers(down_pct, first_use, expected):
    assert calc.va_funding_fee_rate(down_pct, first_use) == expected


def test_exempt_borrower_pays_no_funding_fee():
    assert calc.va_funding_fee_rate(0.0, first_use=False, exempt=True) == 0.0


def test_non_va_loan_has_no_funding_fee():
    assert calc.funding_fee(make_inputs(use_va_loan=False, va_fee_exempt=False)) == 0.0


def test_financed_funding_fee_is_added_to_loan_not_cash():
    inputs = make_inputs(purchase_price=400_000, va_fee_exempt=False, finance_funding_fee=True)
    fee = 400_000 * 0.0215  # $8,600
    assert calc.funding_fee(inputs) == pytest.approx(fee)
    assert calc.loan_amount(inputs) == pytest.approx(400_000 + fee)
    assert calc.cash_needed_breakdown(inputs)["VA funding fee (paid in cash)"] == 0.0


def test_cash_funding_fee_is_added_to_cash_not_loan():
    inputs = make_inputs(purchase_price=400_000, va_fee_exempt=False, finance_funding_fee=False)
    fee = 400_000 * 0.0215
    assert calc.loan_amount(inputs) == pytest.approx(400_000)
    breakdown = calc.cash_needed_breakdown(inputs)
    assert breakdown["VA funding fee (paid in cash)"] == pytest.approx(fee)
    assert breakdown["Total"] == pytest.approx(9_000 + 6_000 + fee)


def test_zero_down_still_needs_cash():
    assert calc.cash_needed_breakdown(make_inputs())["Total"] == pytest.approx(15_000)


# --- Investor view -----------------------------------------------------------------

def test_investor_view_hand_calculated_example():
    result = calc.investor_view(make_inputs())
    # GPR = 1,500 x 2 x 12; effective = 95% of that.
    assert result["gross_potential_rent"] == pytest.approx(36_000)
    assert result["effective_income"] == pytest.approx(34_200)
    # Taxes 3,000 + insurance 1,200 + maintenance 1,800 + capex 1,800 + utilities 1,200.
    assert result["operating_expenses"] == pytest.approx(9_000)
    assert result["noi"] == pytest.approx(25_200)
    assert result["cap_rate"] == pytest.approx(0.084)
    assert result["monthly_pi"] == pytest.approx(1_798.65, abs=0.01)
    assert result["monthly_cash_flow"] == pytest.approx(2_100 - 1_798.65, abs=0.01)
    assert result["dscr"] == pytest.approx(25_200 / (1_798.65 * 12), abs=0.001)
    assert result["break_even_occupancy"] == pytest.approx((9_000 + 1_798.65 * 12) / 36_000, abs=0.001)
    assert result["cash_on_cash"] == pytest.approx(result["annual_cash_flow"] / 15_000)


def test_noi_excludes_debt_service():
    cheap_loan = calc.investor_view(make_inputs(interest_rate=0.02))
    pricey_loan = calc.investor_view(make_inputs(interest_rate=0.09))
    assert cheap_loan["noi"] == pytest.approx(pricey_loan["noi"])
    assert cheap_loan["monthly_cash_flow"] > pricey_loan["monthly_cash_flow"]


def test_full_vacancy_means_no_income_and_no_crash():
    result = calc.investor_view(make_inputs(vacancy_rate=1.0, management_rate=0.08))
    assert result["effective_income"] == 0.0
    assert result["noi"] == pytest.approx(-result["operating_expenses"])
    assert result["monthly_cash_flow"] < 0


def test_no_debt_gives_undefined_dscr():
    result = calc.investor_view(make_inputs(down_payment=300_000))
    assert result["annual_debt_service"] == 0.0
    assert result["dscr"] is None


def test_no_cash_invested_gives_undefined_cash_on_cash():
    result = calc.investor_view(make_inputs(closing_costs=0, reserves=0))
    assert result["cash_on_cash"] is None


def test_zero_rentable_units_gives_zero_rent_and_undefined_break_even():
    ops = calc.annual_operations(make_inputs(), rented_units=0)
    assert ops["gross_potential_rent"] == 0.0
    assert ops["effective_income"] == 0.0
    assert calc.safe_divide(ops["operating_expenses"], ops["gross_potential_rent"]) is None


# --- Owner-occupant view ---------------------------------------------------------------

def test_owner_view_counts_only_other_units_as_rent():
    result = calc.owner_view(make_inputs())
    assert result["rented_units"] == 1
    assert result["gross_potential_rent"] == pytest.approx(1_500 * 12)
    assert result["monthly_effective_rent"] == pytest.approx(1_425)


def test_owner_view_net_housing_cost():
    result = calc.owner_view(make_inputs())
    # Costs are for the whole building: P&I 1,798.65 + expenses 750, minus 1,425 rent.
    assert result["monthly_operating_expenses"] == pytest.approx(750)
    assert result["net_housing_cost"] == pytest.approx(1_798.65 + 750 - 1_425, abs=0.01)
    assert result["monthly_savings_vs_renting"] == pytest.approx(1_600 - result["net_housing_cost"])


# --- Validation ----------------------------------------------------------------------

def test_valid_inputs_have_no_errors():
    assert calc.validate_inputs(make_inputs()) == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"purchase_price": -1},
        {"purchase_price": 0},
        {"down_payment": -5},
        {"down_payment": 400_000},
        {"vacancy_rate": 1.5},
        {"interest_rate": -0.01},
        {"owner_units": 2},
        {"units": 5},
        {"insurance_annual": -100},
    ],
)
def test_invalid_inputs_are_reported(overrides):
    assert calc.validate_inputs(make_inputs(**overrides)) != []


# --- Short-term rental ---------------------------------------------------------------

def test_str_unit_monthly():
    result = calc.str_unit_monthly(
        nightly_rate=100, occupancy_rate=0.6, platform_fee_rate=0.15,
        cleaning_monthly=200, extra_costs_monthly=100,
    )
    gross = 100 * 0.6 * 365 / 12
    assert result["gross_revenue"] == pytest.approx(gross)
    assert result["net_revenue"] == pytest.approx(gross * 0.85 - 300)


# --- Projection and sensitivity ---------------------------------------------------------

def test_projection_shape_and_identities():
    table = calc.project(make_inputs(), view="investor", years=5,
                         appreciation_rate=0.03, rent_growth_rate=0.0, expense_growth_rate=0.0)
    assert list(table["year"]) == [1, 2, 3, 4, 5]
    assert table["property_value"].iloc[0] == pytest.approx(300_000 * 1.03)
    assert (table["equity"] == table["property_value"] - table["loan_balance"]).all()
    assert table["loan_balance"].is_monotonic_decreasing
    assert table["cumulative_cash_flow"].iloc[-1] == pytest.approx(table["annual_cash_flow"].sum())
    # With no growth, year-1 cash flow matches the investor view.
    assert table["annual_cash_flow"].iloc[0] == pytest.approx(calc.investor_view(make_inputs())["annual_cash_flow"])


def test_projection_rejects_unknown_view():
    with pytest.raises(ValueError):
        calc.project(make_inputs(), view="landlord")


def test_sensitivity_directions():
    table = calc.sensitivity(make_inputs(), view="owner").set_index("input")
    rent = table.loc["Rent (±10%)"]
    rate = table.loc["Interest rate (±1 pt)"]
    # Higher rent lowers the owner's cost; a higher interest rate raises it.
    assert rent["input_up"] < rent["base"] < rent["input_down"]
    assert rate["input_down"] < rate["base"] < rate["input_up"]
    assert table["swing"].is_monotonic_decreasing
