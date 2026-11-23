---
name: subscription-billing
description: Design and review subscription billing - plans and prices, trials, upgrades and downgrades with proration, metered and usage-based billing, invoices, taxes, failed-payment retries and dunning, cancellations, grace periods and entitlement sync - whether built on Stripe Billing, Razorpay Subscriptions, Chargebee, Paddle or in-house. Use when building SaaS pricing, fixing access that does not match what a customer paid, handling payment failures, or reviewing subscription and entitlement code.
---

# Subscription billing

Most billing bugs are one of two things: customers get access they did not pay
for, or lose access they did pay for. Design so the **billing provider is the
source of truth for money** and **your app is the source of truth for access**,
kept in sync by webhooks and a periodic reconciliation.

## Model

| Concept | Notes |
|---|---|
| Product | What you sell (Pro plan). |
| Price | Amount, currency, interval (month/year), and model: flat, per-seat, tiered, volume or metered. Prices are immutable; create a new one to change pricing and migrate customers deliberately. |
| Subscription | Customer + price(s) + status + current period. |
| Invoice | What is owed for a period; has line items, tax, discounts and a payment status. |
| Entitlement | What the customer may use now, derived from subscription status in your app. |

## Lifecycle and access

Map provider statuses to access in **one** function and test it:

| Status (Stripe naming) | Typical access |
|---|---|
| `trialing` | full |
| `active` | full |
| `past_due` | keep access during the retry window (grace period), show a banner |
| `unpaid` | restrict (retries exhausted) |
| `incomplete` | none yet (first payment needs action or failed) |
| `incomplete_expired` | none |
| `canceled` | none, or until period end if cancelled at period end |
| `paused` | none (or read-only) |

Provider names differ (Razorpay uses `created`, `authenticated`, `active`,
`pending`, `halted`, `paused`, `cancelled`, `completed`, `expired`), so map each provider explicitly.

## Proration and plan changes

- Upgrades: usually immediate, charging the prorated difference now (or on the
  next invoice). State which in the UI before the customer confirms.
- Downgrades: usually at period end, to avoid refunds and abuse.
- Seat changes: decide whether removing seats credits immediately or at renewal.
- Annual -> monthly switches and currency changes are new subscriptions in most
  systems; do not hand-roll them.
- Preview the invoice (Stripe: "create preview invoice", formerly "upcoming
  invoice"; other providers have equivalents) and show
  the exact amount before confirming.

## Usage-based billing

- Record usage as **idempotent events** (event id + customer + quantity +
  timestamp) in your own store first, then report aggregates to the provider.
- Decide the aggregation (sum, max, last) and the cut-off timezone.
- Late events after an invoice is finalised need a policy: next invoice or a
  credit note.
- Show customers live usage and alerts before thresholds; surprise invoices
  cause chargebacks.

## Failed payments and dunning

- Use the provider's smart retries (or a schedule such as day 1, 3, 5, 7) and
  email the customer at each step with a link to update the payment method.
- Card updater services and "card expiring" emails cut involuntary churn.
- SCA: off-session renewals in Europe and India can require authentication;
  handle the "requires action" outcome by emailing a payment link.
- After the final retry: cancel or mark unpaid, restrict access, keep data for
  a defined period.

## Webhooks to handle (Stripe example)

`customer.subscription.created/updated/deleted`, `invoice.paid`,
`invoice.payment_failed`, `invoice.payment_action_required`,
`customer.subscription.trial_will_end`. Process them idempotently and
out of order: fetch the latest subscription from the API when an event arrives
instead of trusting the event's snapshot (see `webhook-security`).

## Tax and invoices

- Tax rules depend on the seller's and buyer's locations and the product type
  (VAT/GST/sales tax). Use the provider's tax engine or a tax service rather
  than hard-coding rates, and collect the address/tax ID it needs.
- Invoices must be immutable once finalised; corrections are credit notes.
- Keep invoice numbering sequential per legal entity where the law requires it.

## Review checklist

- [ ] One status -> entitlement mapping, unit-tested for every status.
- [ ] Entitlements updated from webhooks **and** a periodic sync job.
- [ ] Webhooks verified, idempotent, order-independent.
- [ ] Plan changes previewed with the exact amount; proration policy documented.
- [ ] Usage events idempotent with a defined cut-off.
- [ ] Dunning emails, grace period and final action defined.
- [ ] No hard-coded tax rates; addresses collected where tax requires them.
- [ ] Amounts in minor units, prices never edited in place.
- [ ] Test clocks / simulated time used to test renewals, trials and dunning.
