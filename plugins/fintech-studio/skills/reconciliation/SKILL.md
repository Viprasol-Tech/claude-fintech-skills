---
name: reconciliation
description: Reconcile money records across systems - your ledger or orders database against Stripe, Razorpay, PayPal or Adyen exports, payout reports and bank statements - matching by reference, amount and date, handling fees, refunds, chargebacks, partial captures, FX and timing differences, and producing an exceptions report. Includes a tested matching script. Use when someone needs to find missing or duplicate payments, explain why payouts do not equal sales, build a daily reconciliation job, or audit that every charge reached the bank.
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/recon.py *)
---

# Payment reconciliation

Reconciliation proves that what your system thinks happened is what the
payment provider and the bank say happened. Every difference is either
explained (fees, timing, FX) or an exception someone must investigate.

## The three-way match

```text
orders / ledger  <->  provider balance transactions  <->  bank statement (payouts)
```

1. **Ledger vs. provider transactions:** every successful charge, refund and
   dispute in the provider export has exactly one ledger entry, and vice versa.
2. **Provider payouts vs. bank:** every payout appears on the bank statement
   with the same amount, a few business days later.
3. **Payout composition:** each payout equals the sum of the provider
   transactions it settles (gross - fees - refunds - disputes +/- adjustments).

Use the provider's **balance transaction / settlement report** (net of fees,
grouped by payout), not the charges list, for step 3.

## Running the matcher

```bash
python ${CLAUDE_SKILL_DIR}/scripts/recon.py ledger.csv provider.csv \
    --left-amount amount --left-date created_at --left-ref order_id \
    --right-amount amount --right-scale 0.01 --right-date created --right-ref metadata_order_id \
    --days 2 --out recon_report.csv
```

- Pass 1 matches on reference; pass 2 on amount (within `--amount-tolerance`)
  and dates within `--days`. Every match is one-to-one.
- `--right-scale 0.01` converts cents to units; `-1` flips signs when one side
  records refunds as positive.
- The exit code is `3` when anything is unresolved, so a scheduled job can alert.
- The report CSV lists `matched:*`, `amount_mismatch`, `unmatched_left` and
  `unmatched_right` rows for investigation.

Before matching, normalise: same sign convention, same unit (major vs. minor),
same timezone for dates, refunds and disputes as separate rows, and gross vs.
net decided for both sides.

## Explaining differences

| Symptom | Usual cause | Check |
|---|---|---|
| Payout < sales | Processing fees, refunds, disputes, reserves | Settlement report line types |
| Charge in provider, not in ledger | Webhook missed or failed, or created outside the app | Webhook delivery logs; replay the event |
| Ledger entry, no provider charge | Payment marked paid before confirmation; test vs. live mix-up | Order state machine; key mode |
| Same amount twice in provider | Double charge (missing idempotency key) or a legitimate repeat purchase | Idempotency keys; customer and timestamp |
| Small amount differences | FX conversion, rounding, partial capture | Currency, captured vs. authorised amount |
| Bank shows payout days later | Payout schedule, weekends, bank holidays | Payout `arrival_date` |
| Unknown negative line | Chargeback or dispute fee | Dispute objects |

## A daily job

1. Pull yesterday's provider balance transactions and payouts by API (paginate;
   use the provider's created/available-on filters in UTC).
2. Pull ledger entries for the same window, plus a buffer of a few days for
   timing differences.
3. Run the matcher; store the report and the summary.
4. Auto-resolve known patterns (fee lines map to the fee account) and open a
   case for everything else, with an owner and an age.
5. Alert when unresolved exceptions are older than N days or the unexplained
   difference exceeds a threshold.
6. Never auto-correct the ledger from the provider file: post an explicit,
   reviewed adjusting entry (see `ledger-design`).

## Review checklist

- [ ] Amounts parsed as decimals or integers in minor units, never floats.
- [ ] Matching is one-to-one; duplicates are surfaced, not silently absorbed.
- [ ] Timezone and cut-off defined (provider days are usually UTC).
- [ ] Fees, refunds, disputes, reserves and FX handled as their own line types.
- [ ] Exceptions have owners and ageing; the job alerts on failure and on drift.
- [ ] Reports are retained for audit.
