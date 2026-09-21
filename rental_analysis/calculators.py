"""
Rental underwriting math from the Rental Analysis Playbook (see CLAUDE.md).

Implements the two Google Sheets calculators in code so results can be
verified before reporting to Kurtis:

- quick_assessment(): "Copy of Investment Property Economics" — one-page
  quick screen, reproduced both as the sheet actually builds it and as a
  realistic-financing version (see CLAUDE.md quirk about the sheet
  financing closing costs and repairs into the loan).
- thirty_year_model(): "Rental Real Estate Analysis" — full 30-year hold
  model with growth rates, appreciation, depreciation, IRR and ROI.

Also provides the buy-box check and target-price/target-rent solvers used
in the per-property workflow.
"""

from __future__ import annotations

DEPRECIATION_YEARS = 27.5  # residential rental property, straight-line


def mortgage_payment(principal: float, annual_rate: float, term_years: float) -> float:
    """Level monthly payment for a fully amortizing loan."""
    monthly_rate = annual_rate / 12
    n = term_years * 12
    if monthly_rate == 0:
        return principal / n
    return principal * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)


def amortization_schedule(principal: float, annual_rate: float, term_years: int) -> list[dict]:
    """Annual amortization summary: interest paid, principal paid, and end-of-year balance."""
    monthly_rate = annual_rate / 12
    payment = mortgage_payment(principal, annual_rate, term_years)
    balance = principal
    months = int(term_years * 12)

    schedule = []
    year_interest = 0.0
    year_principal = 0.0
    for month in range(1, months + 1):
        interest = balance * monthly_rate
        principal_paid = min(payment - interest, balance)
        balance -= principal_paid
        year_interest += interest
        year_principal += principal_paid
        if month % 12 == 0:
            schedule.append({
                "year": month // 12,
                "interest": year_interest,
                "principal": year_principal,
                "end_balance": balance,
            })
            year_interest = 0.0
            year_principal = 0.0
    return schedule


def npv(rate: float, cash_flows: list[float]) -> float:
    return sum(cf / (1 + rate) ** i for i, cf in enumerate(cash_flows))


def irr(cash_flows: list[float], low: float = -0.99, high: float = 10.0,
        tol: float = 1e-7, max_iter: int = 200) -> float:
    """Internal rate of return via bisection (no external deps)."""
    f_low = npv(low, cash_flows)
    f_high = npv(high, cash_flows)
    if f_low * f_high > 0:
        raise ValueError("IRR not bracketed for the given cash flows/range")

    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = npv(mid, cash_flows)
        if abs(f_mid) < tol:
            return mid
        if f_low * f_mid < 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2


def quick_assessment(
    price: float,
    closing_costs: float,
    repairs: float,
    monthly_rent: float,
    annual_operating_expenses: float,
    interest_rate: float,
    term_years: int = 30,
) -> dict:
    """
    "Copy of Investment Property Economics" quick screen.

    Returns both:
    - "sheet": the formulas as the sheet actually computes them (finances
      closing costs and repairs into the loan).
    - "realistic": loan = 80% of price only; down + closing + repairs paid
      in cash, the way a real lender underwrites it.
    """
    annual_rent = monthly_rent * 12
    noi = annual_rent - annual_operating_expenses
    cap_rate = noi / price

    total_investment = price + closing_costs + repairs
    sheet_down_payment = 0.20 * total_investment
    sheet_loan_amount = 0.80 * total_investment
    sheet_debt_service = mortgage_payment(sheet_loan_amount, interest_rate, term_years) * 12
    sheet_cash_flow = noi - sheet_debt_service
    sheet_coc = sheet_cash_flow / (sheet_down_payment + closing_costs)

    realistic_loan_amount = 0.80 * price
    realistic_down_payment = price - realistic_loan_amount
    realistic_cash_in = realistic_down_payment + closing_costs + repairs
    realistic_debt_service = mortgage_payment(realistic_loan_amount, interest_rate, term_years) * 12
    realistic_cash_flow = noi - realistic_debt_service
    realistic_coc = realistic_cash_flow / realistic_cash_in

    return {
        "noi": noi,
        "cap_rate": cap_rate,
        "sheet": {
            "total_investment": total_investment,
            "down_payment": sheet_down_payment,
            "loan_amount": sheet_loan_amount,
            "debt_service": sheet_debt_service,
            "annual_cash_flow": sheet_cash_flow,
            "monthly_cash_flow": sheet_cash_flow / 12,
            "cash_on_cash": sheet_coc,
        },
        "realistic": {
            "down_payment": realistic_down_payment,
            "loan_amount": realistic_loan_amount,
            "cash_in": realistic_cash_in,
            "debt_service": realistic_debt_service,
            "annual_cash_flow": realistic_cash_flow,
            "monthly_cash_flow": realistic_cash_flow / 12,
            "cash_on_cash": realistic_coc,
        },
    }


def thirty_year_model(
    purchase_price: float,
    monthly_rent: float,
    property_value: float | None = None,
    down_pct: float = 0.20,
    interest_rate: float = 0.07,
    term_years: int = 30,
    vacancy_pct: float = 0.05,
    maintenance_pct: float = 0.05,
    management_pct: float = 0.08,
    monthly_taxes: float = 0.0,
    monthly_insurance: float = 0.0,
    hoa: float = 0.0,
    utilities: float = 0.0,
    misc: float = 0.0,
    rent_growth: float = 0.03,
    tax_growth: float = 0.03,
    util_growth: float = 0.04,
    appreciation: float = 0.04,
    building_pct: float = 0.75,
    closing_buy_pct: float = 0.03,
    closing_sell_pct: float = 0.08,
    hold_years: int = 30,
) -> dict:
    """
    "Rental Real Estate Analysis" 30-year hold model.

    Note: unlike the sheet, cap rate here is NOI / purchase price every
    year (the sheet's quirk of using the appreciated value is not
    reproduced — this is the corrected version used for reporting).
    """
    if property_value is None:
        property_value = purchase_price

    down_payment = purchase_price * down_pct
    loan_amount = purchase_price - down_payment
    closing_costs = purchase_price * closing_buy_pct
    cash_invested = down_payment + closing_costs

    schedule = amortization_schedule(loan_amount, interest_rate, term_years)
    monthly_payment = mortgage_payment(loan_amount, interest_rate, term_years)
    annual_debt_service = monthly_payment * 12

    annual_depreciation = (purchase_price * building_pct) / DEPRECIATION_YEARS

    rent = monthly_rent * 12
    taxes = monthly_taxes * 12
    insurance = monthly_insurance * 12
    hoa_annual = hoa * 12
    util_misc = (utilities + misc) * 12

    years = []
    for year in range(1, hold_years + 1):
        vacancy_loss = rent * vacancy_pct
        egi = rent - vacancy_loss
        maintenance = rent * maintenance_pct
        management = rent * management_pct
        operating_expenses = maintenance + management + taxes + insurance + hoa_annual + util_misc
        noi = egi - operating_expenses

        year_debt = schedule[year - 1] if year <= len(schedule) else {"principal": 0.0, "end_balance": 0.0}
        debt_service = annual_debt_service if year <= term_years else 0.0
        cash_flow = noi - debt_service

        current_value = property_value * ((1 + appreciation) ** year)
        loan_balance = year_debt["end_balance"]
        equity = current_value - loan_balance

        years.append({
            "year": year,
            "rent": rent,
            "noi": noi,
            "cap_rate": noi / purchase_price,
            "annual_cash_flow": cash_flow,
            "monthly_cash_flow": cash_flow / 12,
            "cash_on_cash": cash_flow / cash_invested,
            "principal_paydown": year_debt["principal"],
            "loan_balance": loan_balance,
            "property_value": current_value,
            "equity": equity,
            "depreciation": annual_depreciation,
        })

        rent *= (1 + rent_growth)
        taxes *= (1 + tax_growth)
        util_misc *= (1 + util_growth)

    exit_year = years[-1]
    sale_price = exit_year["property_value"]
    selling_costs = sale_price * closing_sell_pct
    net_sale_proceeds = sale_price - selling_costs - exit_year["loan_balance"]

    cash_flows = [-cash_invested] + [y["annual_cash_flow"] for y in years]
    cash_flows[-1] += net_sale_proceeds
    irr_value = irr(cash_flows)

    total_operating_cash_flow = sum(y["annual_cash_flow"] for y in years)
    roi = (total_operating_cash_flow + net_sale_proceeds) / cash_invested

    return {
        "down_payment": down_payment,
        "closing_costs": closing_costs,
        "cash_invested": cash_invested,
        "monthly_payment": monthly_payment,
        "years": years,
        "sale_price": sale_price,
        "net_sale_proceeds": net_sale_proceeds,
        "irr": irr_value,
        "roi": roi,
    }


def buy_box_check(
    monthly_cash_flow: float,
    cash_on_cash: float,
    cap_rate: float,
    monthly_rent: float,
    purchase_price: float,
    min_cash_flow: float = 200,
    min_coc: float = 0.08,
    min_cap_rate: float = 0.07,
) -> dict:
    """
    Buy box from the playbook: positive cash flow (>= $200/door), CoC >= 8%,
    cap rate >= 7%. The 1% rule is a screen only, not a deal-breaker.
    """
    one_percent_ratio = monthly_rent / purchase_price
    checks = {
        "cash_flow": monthly_cash_flow >= min_cash_flow,
        "cash_on_cash": cash_on_cash >= min_coc,
        "cap_rate": cap_rate >= min_cap_rate,
        "one_percent_rule": one_percent_ratio >= 0.01,
    }
    passes = checks["cash_flow"] and checks["cash_on_cash"] and checks["cap_rate"]
    return {
        "checks": checks,
        "one_percent_ratio": one_percent_ratio,
        "verdict": "Buy" if passes else "Pass",
    }


def _quick_assessment_passes(
    price, monthly_rent, annual_operating_expenses, interest_rate, term_years,
    closing_pct, repairs, min_cash_flow, min_coc, min_cap_rate,
) -> bool:
    closing_costs = price * closing_pct
    result = quick_assessment(
        price, closing_costs, repairs, monthly_rent,
        annual_operating_expenses, interest_rate, term_years,
    )
    realistic = result["realistic"]
    return (
        realistic["monthly_cash_flow"] >= min_cash_flow
        and realistic["cash_on_cash"] >= min_coc
        and result["cap_rate"] >= min_cap_rate
    )


def solve_target_price(
    monthly_rent: float,
    annual_operating_expenses: float,
    interest_rate: float,
    term_years: int = 30,
    closing_pct: float = 0.03,
    repairs: float = 0.0,
    min_cash_flow: float = 200,
    min_coc: float = 0.08,
    min_cap_rate: float = 0.07,
    price_low: float = 1_000,
    price_high: float = 10_000_000,
    tol: float = 1.0,
    max_iter: int = 100,
) -> float | None:
    """
    Highest purchase price (realistic financing) that still clears every
    buy-box threshold, holding rent and operating expenses fixed.
    Returns None if even price_low fails the buy box.
    """
    def passes(price):
        return _quick_assessment_passes(
            price, monthly_rent, annual_operating_expenses, interest_rate,
            term_years, closing_pct, repairs, min_cash_flow, min_coc, min_cap_rate,
        )

    if not passes(price_low):
        return None
    if passes(price_high):
        return price_high

    low, high = price_low, price_high
    for _ in range(max_iter):
        mid = (low + high) / 2
        if passes(mid):
            low = mid
        else:
            high = mid
        if high - low < tol:
            break
    return low


def solve_target_rent(
    purchase_price: float,
    annual_operating_expenses: float,
    interest_rate: float,
    term_years: int = 30,
    closing_pct: float = 0.03,
    repairs: float = 0.0,
    min_cash_flow: float = 200,
    min_coc: float = 0.08,
    min_cap_rate: float = 0.07,
    rent_low: float = 0.0,
    rent_high: float = 100_000,
    tol: float = 1.0,
    max_iter: int = 100,
) -> float | None:
    """Lowest monthly rent (at the given price) that clears every buy-box threshold."""
    def passes(rent):
        return _quick_assessment_passes(
            purchase_price, rent, annual_operating_expenses, interest_rate,
            term_years, closing_pct, repairs, min_cash_flow, min_coc, min_cap_rate,
        )

    if not passes(rent_high):
        return None
    if passes(rent_low):
        return rent_low

    low, high = rent_low, rent_high
    for _ in range(max_iter):
        mid = (low + high) / 2
        if passes(mid):
            high = mid
        else:
            low = mid
        if high - low < tol:
            break
    return high
