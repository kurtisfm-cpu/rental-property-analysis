import unittest

from rental_analysis import (
    amortization_schedule,
    buy_box_check,
    irr,
    mortgage_payment,
    quick_assessment,
    solve_target_price,
    solve_target_rent,
    thirty_year_model,
)


class MortgagePaymentTests(unittest.TestCase):
    def test_known_payment(self):
        # $200,000 loan, 6% APR, 30 years -> ~$1,199.10/month (standard reference value).
        payment = mortgage_payment(200_000, 0.06, 30)
        self.assertAlmostEqual(payment, 1199.10, places=1)

    def test_zero_rate_is_straight_line(self):
        payment = mortgage_payment(120_000, 0.0, 10)
        self.assertAlmostEqual(payment, 120_000 / 120, places=6)


class AmortizationScheduleTests(unittest.TestCase):
    def test_full_term_pays_off_loan(self):
        schedule = amortization_schedule(250_000, 0.07, 30)
        self.assertEqual(len(schedule), 30)
        self.assertAlmostEqual(schedule[-1]["end_balance"], 0.0, places=1)
        total_principal = sum(year["principal"] for year in schedule)
        self.assertAlmostEqual(total_principal, 250_000, places=1)

    def test_balance_decreases_every_year(self):
        schedule = amortization_schedule(300_000, 0.065, 30)
        balances = [year["end_balance"] for year in schedule]
        self.assertEqual(balances, sorted(balances, reverse=True))


class QuickAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.price = 300_000
        self.closing_costs = 9_000  # 3%
        self.repairs = 15_000
        self.monthly_rent = 2_500
        self.annual_operating_expenses = 6_000
        self.interest_rate = 0.07

    def test_sheet_formulas_as_built(self):
        result = quick_assessment(
            self.price, self.closing_costs, self.repairs, self.monthly_rent,
            self.annual_operating_expenses, self.interest_rate,
        )
        sheet = result["sheet"]

        total_investment = self.price + self.closing_costs + self.repairs
        self.assertAlmostEqual(sheet["total_investment"], total_investment)
        self.assertAlmostEqual(sheet["down_payment"], 0.20 * total_investment)
        self.assertAlmostEqual(sheet["loan_amount"], 0.80 * total_investment)

        # NOI and cap rate are financing-independent.
        self.assertAlmostEqual(result["noi"], 30_000 - 6_000)
        self.assertAlmostEqual(result["cap_rate"], 24_000 / 300_000)

        expected_debt_service = mortgage_payment(sheet["loan_amount"], self.interest_rate, 30) * 12
        expected_cash_flow = result["noi"] - expected_debt_service
        self.assertAlmostEqual(sheet["annual_cash_flow"], expected_cash_flow)
        self.assertAlmostEqual(
            sheet["cash_on_cash"],
            expected_cash_flow / (sheet["down_payment"] + self.closing_costs),
        )

    def test_realistic_financing_differs_from_sheet(self):
        result = quick_assessment(
            self.price, self.closing_costs, self.repairs, self.monthly_rent,
            self.annual_operating_expenses, self.interest_rate,
        )
        realistic = result["realistic"]
        sheet = result["sheet"]

        # Realistic loan is 80% of price only, not 80% of price+closing+repairs.
        self.assertAlmostEqual(realistic["loan_amount"], 0.80 * self.price)
        self.assertAlmostEqual(realistic["down_payment"], 0.20 * self.price)
        self.assertAlmostEqual(
            realistic["cash_in"],
            realistic["down_payment"] + self.closing_costs + self.repairs,
        )
        self.assertNotAlmostEqual(realistic["loan_amount"], sheet["loan_amount"])

        # Smaller loan -> smaller debt service -> more cash flow than the sheet's version.
        self.assertGreater(realistic["annual_cash_flow"], sheet["annual_cash_flow"])

        # Cap rate is unaffected by financing structure.
        self.assertAlmostEqual(result["cap_rate"], 24_000 / 300_000)


class ThirtyYearModelTests(unittest.TestCase):
    def test_year_one_matches_inputs(self):
        result = thirty_year_model(
            purchase_price=250_000,
            monthly_rent=2_000,
            monthly_taxes=200,
            monthly_insurance=80,
            hold_years=10,
        )
        self.assertEqual(len(result["years"]), 10)

        year1 = result["years"][0]
        annual_rent = 2_000 * 12
        vacancy_loss = annual_rent * 0.05
        egi = annual_rent - vacancy_loss
        expenses = (
            annual_rent * 0.05  # maintenance
            + annual_rent * 0.08  # management
            + 200 * 12  # taxes
            + 80 * 12  # insurance
        )
        expected_noi = egi - expenses
        self.assertAlmostEqual(year1["noi"], expected_noi, places=2)
        self.assertAlmostEqual(year1["cap_rate"], expected_noi / 250_000, places=6)

    def test_equity_grows_and_loan_balance_shrinks(self):
        result = thirty_year_model(
            purchase_price=250_000, monthly_rent=2_000, hold_years=15,
        )
        years = result["years"]
        balances = [y["loan_balance"] for y in years]
        equities = [y["equity"] for y in years]

        self.assertEqual(balances, sorted(balances, reverse=True))
        self.assertGreater(equities[-1], equities[0])

    def test_irr_is_finite_and_reasonable(self):
        result = thirty_year_model(
            purchase_price=250_000, monthly_rent=2_200, hold_years=10,
        )
        self.assertTrue(-1.0 < result["irr"] < 2.0)


class BuyBoxCheckTests(unittest.TestCase):
    def test_passes_ignores_one_percent_rule(self):
        result = buy_box_check(
            monthly_cash_flow=250, cash_on_cash=0.09, cap_rate=0.075,
            monthly_rent=1_600, purchase_price=200_000,
        )
        self.assertEqual(result["verdict"], "Buy")
        self.assertFalse(result["checks"]["one_percent_rule"])  # 1,600/200,000 = 0.8%

    def test_fails_on_cash_flow(self):
        result = buy_box_check(
            monthly_cash_flow=100, cash_on_cash=0.09, cap_rate=0.075,
            monthly_rent=1_600, purchase_price=200_000,
        )
        self.assertEqual(result["verdict"], "Pass")
        self.assertFalse(result["checks"]["cash_flow"])


class SolveTargetTests(unittest.TestCase):
    def test_target_price_clears_buy_box(self):
        target = solve_target_price(
            monthly_rent=2_000,
            annual_operating_expenses=6_000,
            interest_rate=0.07,
        )
        self.assertIsNotNone(target)
        self.assertTrue(
            self._passes_at_price(target, monthly_rent=2_000, annual_operating_expenses=6_000)
        )
        # A meaningfully higher price should no longer clear the bar.
        self.assertFalse(
            self._passes_at_price(target * 1.05, monthly_rent=2_000, annual_operating_expenses=6_000)
        )

    def test_target_price_none_when_rent_too_low(self):
        target = solve_target_price(
            monthly_rent=200,
            annual_operating_expenses=6_000,
            interest_rate=0.07,
        )
        self.assertIsNone(target)

    def test_target_rent_clears_buy_box(self):
        target_rent = solve_target_rent(
            purchase_price=300_000,
            annual_operating_expenses=6_000,
            interest_rate=0.07,
        )
        self.assertIsNotNone(target_rent)
        self.assertTrue(
            self._passes_at_price(300_000, monthly_rent=target_rent, annual_operating_expenses=6_000)
        )
        self.assertFalse(
            self._passes_at_price(
                300_000, monthly_rent=target_rent * 0.95, annual_operating_expenses=6_000
            )
        )

    @staticmethod
    def _passes_at_price(price, monthly_rent, annual_operating_expenses, interest_rate=0.07):
        result = quick_assessment(
            price, price * 0.03, 0.0, monthly_rent, annual_operating_expenses, interest_rate,
        )
        realistic = result["realistic"]
        return (
            realistic["monthly_cash_flow"] >= 200
            and realistic["cash_on_cash"] >= 0.08
            and result["cap_rate"] >= 0.07
        )


if __name__ == "__main__":
    unittest.main()
