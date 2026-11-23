---
name: payments-integration
description: Integrate payment providers without double charges, lost orders or stuck payments - Stripe PaymentIntents and Checkout, Razorpay Orders and Payments, PayPal Orders v2, Adyen - with idempotency keys, a payment state machine, SCA/3D Secure (requires_action), authorise vs. capture, refunds and partial refunds, disputes, test vs. live keys, amounts in minor units and fulfilment driven by verified webhooks. Use when adding checkout or payments to an app, switching providers, debugging duplicate or missing payments, or reviewing payment code before launch.
---

# Payments integration

The provider is the source of truth for whether money moved. Your job is to
create each payment exactly once, track it through its states, and fulfil only
when the provider confirms success.

## Architecture

```text
client                 your server                         provider
  |  checkout ------>  create order (pending) in your DB
  |                    create payment with idempotency key --> PaymentIntent / Order
  |  <-- client secret / order id
  |  confirm in provider UI (card, UPI, wallet, 3DS) ---------> authorises
  |                                     <------- webhook: succeeded / captured / failed
  |                    verify signature, dedupe, re-fetch, mark order paid, fulfil
```

- Never mark an order paid from the client redirect alone; the redirect can be
  lost, forged or arrive before settlement. Fulfil from a verified webhook (see
  `webhook-security`) or a server-side status check.
- Amounts are computed on the server from your own prices, never accepted from
  the client.
- Store the provider's ids (PaymentIntent, order, payment, charge) on your order.

## Idempotency

| Provider | Mechanism |
|---|---|
| Stripe | `Idempotency-Key` header on POST requests (up to 255 chars, UUIDv4 recommended, no sensitive data). The first response is saved and replayed for retries with the same key, including 500s; keys can be pruned after 24 hours; reusing a key with different parameters returns an error. |
| PayPal | `PayPal-Request-Id` header on supported POST calls; a retry returns the original request's latest status. Use different ids for different operations (authorize vs. capture). |
| Adyen | `idempotency-key` header (up to 64 chars, valid for at least 7 days); retry only when the response says `transient-error: true`. |
| Razorpay | No general idempotency header for payments; create **one Order per checkout attempt** and reuse it on retry. Refunds support `X-Refund-Idempotency`; RazorpayX payouts require `X-Payout-Idempotency`. |

Derive the key from your business identity (`order_123:create_payment`), store
it, and reuse it on every retry of that operation. A timeout means "unknown",
not "failed": retry with the same key or look the payment up before creating another.

## State machines

**Stripe PaymentIntent:** `requires_payment_method` -> `requires_confirmation`
-> `requires_action` (3DS/SCA) -> `processing` -> `requires_capture` (manual
capture) -> `succeeded`; or `canceled`. A failed attempt returns to
`requires_payment_method`. Fulfil on `succeeded`. Stripe now steers new
integrations to Checkout Sessions with the Payment Element.

**Razorpay payment:** `created` -> `authorized` -> `captured` (or `failed`,
`refunded`). An authorised payment not captured within **3 days** is
auto-refunded (check your Dashboard capture settings); payments without an Orders API `order_id` cannot be captured.
Enable auto-capture in the Dashboard or capture explicitly.

Model your own order states (`pending`, `requires_action`, `paid`, `failed`,
`refunded`, `partially_refunded`, `disputed`) and allow only valid transitions,
so a late `failed` event cannot overwrite `paid`.

## Keys and environments

- Stripe: `pk_` publishable (safe in the browser), `sk_` secret and `rk_`
  restricted (server only; Stripe recommends restricted keys), `whsec_` webhook
  secret. `_test_` vs. `_live_` prefixes; assert the mode at start-up so a
  test key never reaches production and vice versa.
- Razorpay: `key_id` (public) and `key_secret` (server only); separate webhook secret.
- Keep secrets in a secret manager; rotate on staff changes or exposure.

## Refunds, disputes, captures

- Refunds are new objects with their own ids and webhooks; partial refunds can
  repeat until the captured amount is used up. Make refund requests idempotent.
- Disputes/chargebacks arrive later as their own events, often with a fee;
  record them in the ledger (see `ledger-design`) and respond before the deadline.
- Authorise-then-capture: capture only what you ship; authorisations expire.

## Launch checklist

- [ ] Server-side amounts in minor units, currency-correct (see `money-math`).
- [ ] Idempotency on every create/capture/refund call; timeouts handled as unknown.
- [ ] One order -> at most one successful payment; duplicate attempts detected.
- [ ] Fulfilment only from verified webhooks or server-side status checks.
- [ ] SCA/3DS (`requires_action`) handled on-session and for off-session renewals.
- [ ] Order state machine rejects backwards transitions.
- [ ] Refunds and disputes recorded in the ledger.
- [ ] Test mode end to end with the provider's test cards (success, decline, 3DS,
      insufficient funds) before switching keys.
- [ ] Live/test key mode asserted at start-up; no secret keys in the frontend.
- [ ] No card data touches your servers unless you intend to be in PCI scope
      (use hosted fields / Checkout - see `pci-scope`).
- [ ] Daily reconciliation against the provider's balance transactions.
