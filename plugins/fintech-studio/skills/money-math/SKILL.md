---
name: money-math
description: Handle money correctly in code - integer minor units or decimals instead of floats, ISO 4217 currency exponents (JPY 0, KWD 3) and where payment providers differ from ISO, rounding modes (banker's vs half-up), splitting amounts without losing a cent, FX conversion, percentage fees, tax-inclusive and tax-exclusive maths, and money types in Python, JavaScript/TypeScript, Java, Go and SQL. Includes a tested calculator. Use when writing or reviewing code that stores, calculates, splits, converts, rounds or displays prices, balances, fees, taxes or payouts.
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/money.py *)
---

# Money maths

`0.1 + 0.2 != 0.3` in binary floating point. Small errors become wrong
invoices, unbalanced ledgers and failed reconciliations. Use this skill for any
code that touches amounts, and run the bundled calculator instead of doing
money arithmetic in your head.

## Rules

1. **Never use binary floats for money** (`float`, `double`, JS `number` for
   anything beyond display). Store **integer minor units** (cents, paise, fils)
   or a fixed-point **decimal**, always together with the **currency code**.
2. **The exponent comes from the currency**, never a hard-coded `* 100`.
   ISO 4217: JPY, KRW, VND, CLP, ISK, UGX... have 0 decimals; BHD, IQD, JOD,
   KWD, LYD, OMR, TND have 3; CLF and UYW have 4; most others 2.
3. **Use the provider's exponent table when talking to a provider.** They
   differ from ISO. Examples from Stripe's currency docs: ISK and UGX must be
   sent as two-decimal values ending in `00`; HUF and TWD are charged with two
   decimals but manual payouts must be divisible by 100; Stripe's zero-decimal
   list includes MGA. Razorpay needs three-decimal currencies (KWD, BHD, OMR)
   sent with the last digit 0 (99.991 KWD -> `99990`). Check the provider's
   current currency page.
4. **Round once, at a defined point, with a named mode.** Banker's rounding
   (half-even) avoids bias over many operations; half-up is what most people and
   many tax rules expect. Write down which one each calculation uses.
5. **Splits must sum to the total.** Allocate remainders explicitly (largest
   remainder method), never `total / n` rounded n times.
6. **Never mix currencies** in one sum. Convert with an explicit, recorded rate
   and timestamp, then round in the target currency.
7. **Parse and format at the edges.** Accept strings from users and APIs, convert
   to integers/decimals immediately, and format only for display with the
   locale (`Intl.NumberFormat`, Babel, ICU).

## Calculator

```bash
python ${CLAUDE_SKILL_DIR}/scripts/money.py to-minor 19.99 USD                 # 1999
python ${CLAUDE_SKILL_DIR}/scripts/money.py to-minor 1500 JPY                  # 1500
python ${CLAUDE_SKILL_DIR}/scripts/money.py from-minor 12345 KWD               # 12.345
python ${CLAUDE_SKILL_DIR}/scripts/money.py allocate 10000 USD 1 1 1           # 3334 3333 3333  (always sums to 10000)
python ${CLAUDE_SKILL_DIR}/scripts/money.py allocate 99999 USD 70 20 10        # weighted split
python ${CLAUDE_SKILL_DIR}/scripts/money.py convert 10000 USD INR 83.4517      # 834517 paise
python ${CLAUDE_SKILL_DIR}/scripts/money.py fee 10000 USD --pct 2.9 --fixed 30 # 320
python ${CLAUDE_SKILL_DIR}/scripts/money.py split-tax 11800 INR --rate 18 --inclusive   # net 10000, tax 1800
python ${CLAUDE_SKILL_DIR}/scripts/money.py --rounding half-up to-minor 19.985 USD --round
```

`to-minor` rejects extra precision (19.999 USD) unless you pass `--round`,
rejects ambiguous input such as `1,50` (a European decimal comma), and rejects
unknown currency codes unless you pass `--exponent CODE=N`.
`--json` gives machine-readable output; `--self-test` checks the maths.

## Language cheat sheet

| Language | Use | Avoid |
|---|---|---|
| Python | `decimal.Decimal("19.99")` (from **strings**), `int` minor units | `float`, `Decimal(19.99)` |
| JS / TS | `bigint` or `number` holding **integer** minor units (safe up to 2^53-1), or a decimal library (`decimal.js`, `big.js`, `dinero.js`) | `0.1 + 0.2`, `toFixed()` for maths |
| Java / Kotlin | `BigDecimal` with explicit `RoundingMode`, or `long` minor units; JSR 354 (Moneta) | `double`, `new BigDecimal(0.1)` |
| Go | `int64` minor units, or `shopspring/decimal` | `float64` |
| C# | `decimal` | `double` |
| PostgreSQL | `bigint` minor units, or `numeric(19,4)` + a `currency char(3)` column | `real`, `double precision`, the `money` type (locale-dependent) |
| JSON APIs | integers in minor units or decimal **strings** | JSON floats for amounts |

## Review checklist

- [ ] No float types or float literals in money paths (search for `float`, `double`, `parseFloat`, `toFixed`).
- [ ] Every amount carries its currency; exponent looked up per currency.
- [ ] Provider-specific exponent rules handled at the integration boundary.
- [ ] Rounding mode named and applied once per calculation.
- [ ] Splits and allocations sum exactly to the original.
- [ ] FX conversions store rate, source and timestamp.
- [ ] Totals computed from line items in minor units, then compared with the
      provider's amount before charging.
- [ ] Display formatting is locale-aware and never fed back into calculations.
