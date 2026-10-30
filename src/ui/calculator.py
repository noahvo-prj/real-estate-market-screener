"""Property Calculator tab: investor view and owner-occupant (house hack) view of one property."""

import pandas as pd
import streamlit as st

import config
from src import calculations as calc
from src import charts, scoring

D = config.CALCULATOR_DEFAULTS
P = config.PROJECTION_DEFAULTS

# Session-state defaults for inputs that are not prefilled from a market.
# Percent inputs are stored as percentages here (7.0) and converted to decimals (0.07) on use.
STATE_DEFAULTS = {
    "calc_units": D["units"],
    "calc_owner_units": D["owner_units"],
    "calc_va": D["use_va_loan"],
    "calc_down_pct": 0.0,
    "calc_rate_pct": D["interest_rate"] * 100,
    "calc_term": D["loan_term_years"],
    "calc_va_first_use": D["va_first_use"],
    "calc_va_exempt": D["va_fee_exempt"],
    "calc_finance_fee": D["finance_funding_fee"],
    "calc_insurance": D["insurance_annual"],
    "calc_hoa": D["hoa_monthly"],
    "calc_maintenance_pct": D["maintenance_rate"] * 100,
    "calc_capex_pct": D["capex_rate"] * 100,
    "calc_management_pct": D["management_rate"] * 100,
    "calc_utilities": D["owner_utilities_monthly"],
    "calc_other": D["other_monthly"],
    "calc_reserves": D["reserves"],
    "calc_repairs": D["initial_repairs"],
    "calc_furnishing": D["furnishing"],
    "calc_years": P["years"],
    "calc_appreciation_pct": P["appreciation_rate"] * 100,
    "calc_rent_growth_pct": P["rent_growth_rate"] * 100,
    "calc_expense_growth_pct": P["expense_growth_rate"] * 100,
    "calc_str": False,
    "calc_str_nightly": 150.0,
    "calc_str_occupancy_pct": 60.0,
    "calc_str_platform_pct": 15.0,
    "calc_str_cleaning": 300.0,
    "calc_str_extra": 150.0,
}

# Fallbacks when a market is missing a prefill value.
FALLBACK_PRICE = 350_000.0
FALLBACK_RENT = 1_500.0
FALLBACK_TAX_PCT = 1.0
FALLBACK_VACANCY_PCT = D["vacancy_rate"] * 100


# --- Formatting ---------------------------------------------------------------

def money(value: float | None, decimals: int = 0) -> str:
    if value is None:
        return "n/a"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.{decimals}f}"


def pct(value: float | None, decimals: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{decimals}%}"


def ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}x"


def headline(net_housing_cost: float, comparable_rent: float) -> str:
    """One-sentence rent-vs-own summary for the owner-occupant."""
    if net_housing_cost < 0:
        return (f"The other units would cover all costs and leave you about {money(-net_housing_cost)}/month "
                f"ahead, vs. paying {money(comparable_rent)} to rent a similar unit.")
    return (f"You'd pay about {money(net_housing_cost)}/month to live here vs. "
            f"{money(comparable_rent)} renting a similar unit.")


# --- Prefill ------------------------------------------------------------------

def _apply_prefill(markets: pd.DataFrame) -> None:
    """Copy the chosen market's values into the inputs. Missing values keep the current input."""
    row = markets.set_index("metro").loc[st.session_state["calc_market"]]
    missing = []

    def setval(key, value, transform, fallback):
        if pd.isna(value):
            missing.append(key)
            st.session_state.setdefault(key, fallback)
        else:
            st.session_state[key] = transform(value)

    setval("calc_price", row["zhvi"], lambda v: float(round(v, -3)), FALLBACK_PRICE)
    setval("calc_rent", row["zori"], lambda v: float(round(v, -1)), FALLBACK_RENT)
    setval("calc_comparable_rent", row["zori"], lambda v: float(round(v, -1)), FALLBACK_RENT)
    setval("calc_tax_pct", row["effective_tax_rate"], lambda v: round(v * 100, 2), FALLBACK_TAX_PCT)
    setval("calc_vacancy_pct", row["rental_vacancy_rate"], lambda v: round(v * 100, 1), FALLBACK_VACANCY_PCT)
    st.session_state["calc_closing_costs"] = float(round(st.session_state["calc_price"] * D["closing_cost_rate"], -2))
    st.session_state["calc_prefilled_price"] = st.session_state["calc_price"]
    st.session_state["calc_prefill_missing"] = missing


def _init_state(markets: pd.DataFrame) -> None:
    for key, value in STATE_DEFAULTS.items():
        st.session_state.setdefault(key, value)
    if st.session_state.get("calc_market") not in set(markets["metro"]):
        st.session_state["calc_market"] = _top_market(markets)
        _apply_prefill(markets)


def _top_market(markets: pd.DataFrame) -> str:
    """The #1 market under the default weights, so the calculator opens on a sensible example."""
    if len(markets) < 2:
        return markets["metro"].iloc[0]
    scored = scoring.score_markets(markets, config.WEIGHT_PRESETS[config.DEFAULT_PRESET])
    return scored["metro"].iloc[0]


# --- Inputs -------------------------------------------------------------------

def _inputs_section(markets: pd.DataFrame) -> tuple[calc.PropertyInputs, dict, dict | None]:
    s = st.session_state
    row = markets.set_index("metro").loc[s["calc_market"]]
    zillow_month = row.get("zhvi_month", "")
    acs_year = row.get("acs_year", "")

    with st.expander("Property", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.number_input("Purchase price ($)", min_value=0.0, step=5_000.0, key="calc_price",
                        help="Prefilled from Zillow ZHVI. Replace with a real listing price.")
        c1.caption(f"Prefill: Zillow ZHVI, {zillow_month}. Mostly single-family homes, not duplex prices.")
        c2.selectbox("Number of units", [2, 3, 4], key="calc_units")
        c2.number_input("Units you live in", min_value=0, max_value=3, step=1, key="calc_owner_units",
                        help="Owner-occupied units. Must be fewer than total units.")
        c3.number_input("Monthly rent per rentable unit ($)", min_value=0.0, step=25.0, key="calc_rent",
                        help="Prefilled from Zillow ZORI. Replace with local rent comps for this unit size.")
        c3.caption(f"Prefill: Zillow ZORI, {zillow_month}. All rental types, not a duplex unit's rent.")
        c3.number_input("Rent for a comparable place to live ($/mo)", min_value=0.0, step=25.0,
                        key="calc_comparable_rent",
                        help="What you'd pay to rent a similar home instead. Used for rent-vs-own.")

    with st.expander("Financing", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.toggle("VA loan", key="calc_va")
        c1.number_input("Down payment (% of price)", min_value=0.0, max_value=100.0, step=1.0, key="calc_down_pct")
        c1.caption(f"= {money(s['calc_price'] * s['calc_down_pct'] / 100)}")
        c2.number_input("Interest rate (%)", min_value=0.0, max_value=100.0, step=0.125, format="%.3f",
                        key="calc_rate_pct", help="The default is a placeholder. Use a real lender quote.")
        c2.caption("Default is a placeholder, not today's rate. Enter a real lender quote.")
        c2.selectbox("Loan term (years)", [15, 20, 30], key="calc_term")
        c3.number_input("Closing costs ($)", min_value=0.0, step=500.0, key="calc_closing_costs",
                        help=f"Prefilled at {D['closing_cost_rate']:.0%} of price. Replace with the lender's estimate.")
        if s["calc_va"]:
            v1, v2, v3 = st.columns(3)
            v1.toggle("First VA loan", key="calc_va_first_use")
            v2.toggle("Exempt from funding fee", key="calc_va_exempt",
                      help="For example, Veterans receiving VA disability compensation. Check VA.gov.")
            v3.toggle("Finance the funding fee into the loan", key="calc_finance_fee")
            st.caption(f"Funding fee rates: {config.VA_FUNDING_FEE_SOURCE}")

    with st.expander("Operating costs"):
        c1, c2, c3 = st.columns(3)
        c1.number_input("Property tax rate (% of price per year)", min_value=0.0, max_value=100.0, step=0.05,
                        format="%.2f", key="calc_tax_pct")
        c1.caption(f"Prefill: Census ACS {acs_year}, median taxes / median home value. Varies within a metro.")
        c1.number_input("Insurance ($/year)", min_value=0.0, step=100.0, key="calc_insurance")
        c1.number_input("HOA ($/month)", min_value=0.0, step=25.0, key="calc_hoa")
        c2.number_input("Vacancy (%)", min_value=0.0, max_value=100.0, step=0.5, key="calc_vacancy_pct")
        c2.caption(f"Prefill: Census ACS {acs_year} rental vacancy rate (metro-wide).")
        c2.number_input("Maintenance (% of rent)", min_value=0.0, max_value=100.0, step=0.5, key="calc_maintenance_pct")
        c2.number_input("Capex reserve (% of rent)", min_value=0.0, max_value=100.0, step=0.5, key="calc_capex_pct",
                        help="Savings for big replacements: roof, HVAC, water heater.")
        c3.number_input("Property management (% of rent collected)", min_value=0.0, max_value=100.0, step=0.5,
                        key="calc_management_pct", help="0% if you manage it yourself.")
        c3.number_input("Owner-paid utilities ($/month)", min_value=0.0, step=25.0, key="calc_utilities")
        c3.number_input("Other expenses ($/month)", min_value=0.0, step=25.0, key="calc_other")

    with st.expander("Upfront cash"):
        c1, c2, c3 = st.columns(3)
        c1.number_input("Cash reserves ($)", min_value=0.0, step=500.0, key="calc_reserves",
                        help="Money set aside after closing for surprises. Lenders may require some.")
        c2.number_input("Initial repairs ($)", min_value=0.0, step=500.0, key="calc_repairs")
        c3.number_input("Furnishing ($)", min_value=0.0, step=500.0, key="calc_furnishing",
                        help="Usually only needed for a short-term rental unit.")

    with st.expander("Projection assumptions"):
        c1, c2, c3, c4 = st.columns(4)
        c1.slider("Years to project", 5, 10, key="calc_years")
        c2.number_input("Appreciation (%/yr)", min_value=-20.0, max_value=20.0, step=0.5, key="calc_appreciation_pct")
        c3.number_input("Rent growth (%/yr)", min_value=-20.0, max_value=20.0, step=0.5, key="calc_rent_growth_pct")
        c4.number_input("Expense growth (%/yr)", min_value=-20.0, max_value=20.0, step=0.5,
                        key="calc_expense_growth_pct")

    with st.expander("Optional: short-term rental (one unit)"):
        st.toggle("Model one unit as a short-term rental", key="calc_str")
        st.caption("Short-term rental rules vary by city and can prohibit it entirely. Check local rules first.")
        if s["calc_str"]:
            c1, c2, c3 = st.columns(3)
            c1.number_input("Nightly rate ($)", min_value=0.0, step=5.0, key="calc_str_nightly")
            c1.number_input("Occupancy (%)", min_value=0.0, max_value=100.0, step=1.0, key="calc_str_occupancy_pct")
            c2.number_input("Platform fees (% of revenue)", min_value=0.0, max_value=100.0, step=0.5,
                            key="calc_str_platform_pct")
            c2.number_input("Cleaning ($/month)", min_value=0.0, step=25.0, key="calc_str_cleaning")
            c3.number_input("Extra utilities and supplies ($/month)", min_value=0.0, step=25.0, key="calc_str_extra")

    inputs = calc.PropertyInputs(
        purchase_price=s["calc_price"],
        rent_per_unit=s["calc_rent"],
        property_tax_rate=s["calc_tax_pct"] / 100,
        comparable_rent=s["calc_comparable_rent"],
        units=s["calc_units"],
        owner_units=s["calc_owner_units"],
        down_payment=s["calc_price"] * s["calc_down_pct"] / 100,
        interest_rate=s["calc_rate_pct"] / 100,
        loan_term_years=s["calc_term"],
        use_va_loan=s["calc_va"],
        va_first_use=s["calc_va_first_use"],
        va_fee_exempt=s["calc_va_exempt"],
        finance_funding_fee=s["calc_finance_fee"],
        closing_costs=s["calc_closing_costs"],
        insurance_annual=s["calc_insurance"],
        hoa_monthly=s["calc_hoa"],
        vacancy_rate=s["calc_vacancy_pct"] / 100,
        maintenance_rate=s["calc_maintenance_pct"] / 100,
        capex_rate=s["calc_capex_pct"] / 100,
        management_rate=s["calc_management_pct"] / 100,
        owner_utilities_monthly=s["calc_utilities"],
        other_monthly=s["calc_other"],
        reserves=s["calc_reserves"],
        initial_repairs=s["calc_repairs"],
        furnishing=s["calc_furnishing"],
    )
    projection = {
        "years": s["calc_years"],
        "appreciation_rate": s["calc_appreciation_pct"] / 100,
        "rent_growth_rate": s["calc_rent_growth_pct"] / 100,
        "expense_growth_rate": s["calc_expense_growth_pct"] / 100,
    }
    str_inputs = None
    if s["calc_str"]:
        str_inputs = {
            "nightly_rate": s["calc_str_nightly"],
            "occupancy_rate": s["calc_str_occupancy_pct"] / 100,
            "platform_fee_rate": s["calc_str_platform_pct"] / 100,
            "cleaning_monthly": s["calc_str_cleaning"],
            "extra_costs_monthly": s["calc_str_extra"],
        }
    return inputs, projection, str_inputs


# --- Results ------------------------------------------------------------------

def _metric_table(rows: list[tuple[str, str]]) -> None:
    st.dataframe(pd.DataFrame(rows, columns=["Metric", "Value"]), hide_index=True, width="stretch")


def _owner_section(owner: dict) -> None:
    st.markdown("#### Owner-occupant view (house hack)")
    st.caption("You live in one unit. Only the other units pay rent; you pay all the building's costs.")
    _metric_table([
        ("Mortgage payment (principal and interest)", money(owner["monthly_pi"]) + "/mo"),
        ("Operating expenses (whole property)", money(owner["monthly_operating_expenses"]) + "/mo"),
        (f"Rent from the other {owner['rented_units']} unit(s), after vacancy",
         "-" + money(owner["monthly_effective_rent"]) + "/mo"),
        ("Your net housing cost (negative = you come out ahead)", money(owner["net_housing_cost"]) + "/mo"),
        ("Renting a comparable place instead", money(owner["comparable_rent"]) + "/mo"),
    ])
    st.caption("Your own unit is never counted as rental income in this view.")


def _investor_section(investor: dict) -> None:
    st.markdown("#### Investor view (all units rented)")
    st.caption("The same property as if every unit, including yours, were rented out.")
    _metric_table([
        ("Gross potential rent", money(investor["gross_potential_rent"]) + "/yr"),
        ("Effective rental income (after vacancy)", money(investor["effective_income"]) + "/yr"),
        ("Operating expenses", money(investor["operating_expenses"]) + "/yr"),
        ("Net operating income (NOI)", money(investor["noi"]) + "/yr"),
        ("Cap rate", pct(investor["cap_rate"], 2)),
        ("Monthly cash flow", money(investor["monthly_cash_flow"]) + "/mo"),
        ("Annual cash flow", money(investor["annual_cash_flow"]) + "/yr"),
        ("Debt service coverage ratio (DSCR)", ratio(investor["dscr"])),
        ("Break-even occupancy", pct(investor["break_even_occupancy"])),
        ("Cash-on-cash return", pct(investor["cash_on_cash"])),
    ])
    st.caption(
        "NOI and cap rate exclude the mortgage. Cash-on-cash = annual cash flow / total cash needed at purchase. "
        "DSCR is shown for reference: owner-occupied VA loans are underwritten on the borrower's "
        "debt-to-income ratio, not DSCR."
    )


def _cash_needed_section(inputs: calc.PropertyInputs) -> None:
    st.markdown("#### Cash needed at purchase")
    breakdown = calc.cash_needed_breakdown(inputs)
    fee = calc.funding_fee(inputs)
    rows = [(item, money(amount)) for item, amount in breakdown.items()]
    _metric_table(rows)
    if inputs.use_va_loan:
        where = "added to the loan" if inputs.finance_funding_fee else "paid in cash at closing"
        st.caption(f"VA funding fee: {money(fee)} ({where}). Loan amount: {money(calc.loan_amount(inputs))}.")
    if inputs.down_payment == 0:
        st.caption("0% down does not mean $0 invested: closing costs and reserves still need cash.")


def _str_section(inputs: calc.PropertyInputs, owner: dict, str_inputs: dict) -> None:
    st.markdown("#### Short-term rental scenario (one unit)")
    result = calc.str_unit_monthly(**str_inputs)
    long_term = inputs.rent_per_unit * (1 - inputs.vacancy_rate)
    difference = result["net_revenue"] - long_term
    c1, c2, c3 = st.columns(3)
    c1.metric("STR net revenue", money(result["net_revenue"]) + "/mo",
              help="Nightly rate x occupancy x 30.4 nights, minus platform fees, cleaning and supplies.")
    c2.metric("Long-term rent for that unit", money(long_term) + "/mo", help="Rent per unit after vacancy.")
    c3.metric("Difference", money(difference) + "/mo")
    if owner["rented_units"] >= 1:
        st.caption(
            f"With one unit as an STR, your net housing cost would be about "
            f"{money(owner['net_housing_cost'] - difference)}/mo. "
            "This ignores furnishing (entered under Upfront cash), extra insurance and STR taxes. "
            "Check local STR rules: some cities prohibit short-term rentals entirely."
        )


def _projection_section(inputs: calc.PropertyInputs, projection: dict, view: str) -> None:
    st.markdown("#### Multi-year projection")
    st.caption(
        "Assumption-driven, not a forecast. Uses the growth rates under Projection assumptions. "
        + ("In the owner view, cash flow is usually negative: it is what you pay to live there."
           if view == "owner" else "")
    )
    table = calc.project(inputs, view=view, **projection)
    st.plotly_chart(charts.projection_chart(table), width="stretch")
    display = table.set_index("year").map(money).reset_index()
    display.columns = [c.replace("_", " ").capitalize() for c in display.columns]
    st.dataframe(display, hide_index=True, width="stretch")


def _sensitivity_section(inputs: calc.PropertyInputs, view: str) -> None:
    st.markdown("#### What moves the numbers most?")
    label = "Net monthly housing cost (lower is better)" if view == "owner" else "Monthly cash flow (higher is better)"
    st.caption(f"Each bar shows {label.split(' (')[0].lower()} when one input moves down or up and everything "
               "else stays the same. Longest bars are the inputs worth checking most carefully.")
    st.plotly_chart(charts.tornado_chart(calc.sensitivity(inputs, view=view), label), width="stretch")


# --- Tab ----------------------------------------------------------------------

def render(markets: pd.DataFrame) -> None:
    st.subheader("Property Calculator")
    st.caption("Evaluate a specific 2-4 unit property, as an investor and as an owner living in one unit.")
    _init_state(markets)

    st.selectbox(
        "Prefill from market", markets["metro"].tolist(), key="calc_market",
        on_change=_apply_prefill, args=(markets,),
        help="Fills price, rent, tax rate and vacancy from the market data. Every value stays editable.",
    )
    if st.session_state.get("calc_prefill_missing"):
        st.info("Some values aren't available for this market and were left at their previous values. "
                "Enter them manually.")
    if st.session_state["calc_price"] == st.session_state.get("calc_prefilled_price"):
        st.warning(
            "The purchase price is still the metro's typical home value, which mostly reflects single-family "
            "homes. Replace it with a real listing price for the property you're considering."
        )

    cards = st.container()
    inputs, projection, str_inputs = _inputs_section(markets)

    errors = calc.validate_inputs(inputs)
    if errors:
        with cards:
            for error in errors:
                st.error(error)
        return

    owner = calc.owner_view(inputs)
    investor = calc.investor_view(inputs)
    cash_total = calc.cash_needed_breakdown(inputs)["Total"]
    lives_there = inputs.owner_units > 0

    with cards:
        c1, c2, c3, c4 = st.columns(4)
        if lives_there and owner["net_housing_cost"] < 0:
            c1.metric("You come out ahead by", money(-owner["net_housing_cost"]) + "/mo",
                      help="Rent from the other units covers the mortgage and all expenses, with this much left over.")
            c2.metric("Renting a comparable place", money(owner["comparable_rent"]) + "/mo")
        elif lives_there:
            c1.metric("Your net housing cost", money(owner["net_housing_cost"]) + "/mo",
                      help="Mortgage + operating expenses - rent from the other units.")
            c2.metric("Renting a comparable place", money(owner["comparable_rent"]) + "/mo")
        else:
            c1.metric("Your net housing cost", "n/a", help="You don't live in a unit in this scenario.")
            c2.metric("Renting a comparable place", "n/a")
        c3.metric("Investor cash flow", money(investor["monthly_cash_flow"]) + "/mo",
                  help="If every unit were rented out.")
        c4.metric("Cash needed at purchase", money(cash_total))
        if lives_there:
            st.markdown(f"**{headline(owner['net_housing_cost'], owner['comparable_rent'])}**")

    st.divider()
    left, right = st.columns(2)
    with left:
        if lives_there:
            _owner_section(owner)
        else:
            st.info("Set 'Units you live in' to 1 or more to see the house-hack view.")
    with right:
        _investor_section(investor)

    with st.expander("Operating expense breakdown (investor view, annual)"):
        _metric_table([(k, money(v)) for k, v in investor["expense_breakdown"].items()])
        st.caption("Maintenance and capex are a share of the whole building's rent. "
                   "Management is a share of rent actually collected. The mortgage is not an operating expense.")

    _cash_needed_section(inputs)
    if str_inputs:
        _str_section(inputs, owner, str_inputs)

    st.divider()
    views = {"Owner-occupant": "owner", "Investor": "investor"} if lives_there else {"Investor": "investor"}
    view = views[st.radio("View for projection and sensitivity", list(views), horizontal=True, key="calc_view")]
    _projection_section(inputs, projection, view)
    _sensitivity_section(inputs, view)
