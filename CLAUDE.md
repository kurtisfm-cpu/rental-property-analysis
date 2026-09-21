# Rental Analysis Playbook

How Claude runs the numbers in this project. Kurtis drops an address or listing; Claude fills the inputs, runs both calculators, and gives a verdict plus a "price it needs to be" answer.

## The two calculators (Google Drive)

**1. Rental Real Estate Analysis** (`1yN4MW7wOt_zDjsbLmq9bw4x27Tpi3FcFCHasUe7TdUg`) — 30-year hold model
- Inputs: property value (est.), purchase price, interest rate, down %, term, monthly rent, vacancy %, maintenance %, management %, monthly taxes, monthly insurance, HOA, utilities, misc; growth rates (rent 3%, tax 3%, utilities/misc 4%), appreciation 4%, building/land 75%, closing costs 3% buy / 8% sell.
- Outputs: cap rate, cash-on-cash, NOI, annual/monthly cash flow, principal paydown, equity by year, depreciation, IRR, ROI.
- Quirks to watch: the "Down Payment $1,000" cell in Basic Purchase Info is stale and doesn't match the 5% down in the mortgage block; Year 1 "appreciation" includes the value-vs-price gap (instant equity), which inflates Year 1 returns. Yearly cap rate uses the appreciated value, not the price.

**2. Copy of Investment Property Economics** (`174I1UwIlfAm43fNMXkrayFLM0l-lSFI4zR2KD01-ztw`) — quick one-page assessment. Tabs already run: 275 Quarter St, 4339 Comet Trl, 716 Larkin Ave (Chattanooga). Also has a mortgage amortization tab (Vertex42) and a San Jose comps/scenario tab (old, not Chattanooga).
- Formulas as built: total investment = price + closing + repairs; down payment = 20% of total investment; loan = 80% of total investment; CoC = annual cash flow ÷ (down payment + closing costs); cap rate = annual NOI ÷ purchase price.
- Quirk: it finances closing costs and repairs inside the loan, which a real lender won't do. Claude reports the realistic version (loan = 80% of price, cash in = down + closing + repairs) alongside the sheet's version when they differ materially.

## Default assumptions (unless Kurtis says otherwise)

| Input | Default | Notes |
| --- | --- | --- |
| Down payment | 20% (investor loan) | |
| Interest rate | Current 30-yr investor rate | Search the day's rate; the sheets' 7% is from 2025 |
| Closing costs (buy) | ~3% of price | |
| Vacancy | 5% of rent | Sheet tabs use a flat $100/mo |
| Maintenance/CapEx | 5% of rent, or $100/mo floor | Raise for older homes |
| Property management | 8–10% of rent | |
| Insurance | ~$80/mo | Confirm with a quote for older or larger homes |
| Property taxes | From county records / listing | Hamilton Co. TN, Walker/Catoosa/Dade Co. GA |
| Rent | Rent comps for the zip + beds/baths | Cite the source |

## Workflow per property

1. Pull listing facts: price, beds/baths, sqft, year built, taxes, HOA, condition (Flexmls if connected, otherwise the listing link or Kurtis's notes).
2. Estimate rent from comps and state the range used.
3. Run the quick assessment (sheet 2 logic) and the 30-year model (sheet 1 logic); verify the math in code before reporting.
4. Report: monthly cash flow, cap rate, CoC, cash needed to close, 5-yr equity.
5. **Target price**: solve for the purchase price that hits the buy-box (below). Also give the rent needed at asking price.
6. Verdict in one line: Buy / Negotiate to $X / Pass.
7. Optionally add a new tab to sheet 2 for the property (copy an existing tab's layout).

## Buy box (confirm/adjust with Kurtis)

- Positive monthly cash flow after all reserves (target $200+/door)
- Cash-on-cash ≥ 8%
- Cap rate ≥ 7%
- 1% rule (rent ÷ price) as a quick screen, not a deal-breaker

## Output format

Short summary table + verdict + target price. Flag every estimated input so Kurtis knows what to verify. Kurtis is a former PE/REIT acquisitions pro: skip the basics, show the underwriting.
