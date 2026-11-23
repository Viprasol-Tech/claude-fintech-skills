---
name: webhook-security
description: Build and review payment webhook handlers that cannot be forged, replayed or double-processed - Stripe-Signature (t= and v1= HMAC-SHA256) verification on the raw body, Razorpay X-Razorpay-Signature, PayPal transmission signature and CRC32 self-verification, Adyen HMAC, timestamp tolerance, constant-time comparison, event-id deduplication, out-of-order delivery, fast 2xx then async processing, and secret rotation. Includes a local signature checker. Use when writing a webhook endpoint, debugging "signature verification failed", or reviewing code that fulfils orders, credits balances or grants access from webhook events.
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/verify_webhook.py *)
---

# Webhook security

A webhook endpoint is a public URL that can move money or grant access. Treat
every request as hostile until its signature is verified, and assume every
genuine event can arrive **late, twice, or out of order**.

## The handler pattern

```text
1. read the RAW body bytes (before any JSON parser touches them)
2. verify the signature against the raw body with the endpoint secret
3. reject if invalid (400) or if the timestamp is outside tolerance
4. dedupe: if event id already processed -> return 2xx, do nothing
5. store the event, return 2xx quickly
6. process asynchronously (queue/worker): fetch the latest object from the
   provider API, apply an idempotent state change, mark the event processed
```

Never trust amounts or statuses from the payload alone for fulfilment; re-fetch
the object (PaymentIntent, order, subscription) by id from the API.

## Stripe

Docs: <https://docs.stripe.com/webhooks>

- Header `Stripe-Signature: t=<unix>,v1=<hex>[,v1=<hex>...]`. The parser must
  tolerate unknown entries and any order. **Only use `t` and `v1`**; ignore `v0`
  (sandbox-only, fake) and any debug entries like `secret=` or `payload=`.
- Signed payload: `"{t}." + raw_body`; HMAC-SHA256 with the endpoint secret
  (`whsec_...`); constant-time compare against **each** `v1` (several appear
  while a secret is rolling - the old secret can stay valid for up to 7 days).
- Tolerance: the official libraries default to 5 minutes. Never set it to 0
  (that disables replay protection).
- Raw body: in Express, mount the webhook route with `express.raw({type: 'application/json'})`
  **before** `express.json()`; in Next.js route handlers use `await req.text()`;
  in Django use `request.body`; in Flask `request.get_data()`.
- Secrets differ for test vs. live and for `stripe listen` vs. the Dashboard
  endpoint - the most common cause of mismatches.
- Delivery: live mode retries for up to 3 days with exponential backoff; 3xx
  redirects count as failures. Order is not guaranteed and duplicates happen:
  dedupe on `event.id` (and on `data.object.id` + `event.type` for the rare
  case of two event objects for one change).

```python
import stripe  # official library: verifies signature + tolerance
event = stripe.Webhook.construct_event(raw_body, sig_header, endpoint_secret)
```

```js
const event = stripe.webhooks.constructEvent(req.body /* Buffer */, req.headers['stripe-signature'], endpointSecret);
```

## Razorpay

Docs: <https://razorpay.com/docs/webhooks/validate-test/>

- Header `X-Razorpay-Signature` = hex HMAC-SHA256 of the **raw body** with the
  **webhook secret** (not the API key secret). Do not parse before verifying.
- Dedupe on the `x-razorpay-event-id` header.
- Respond within 5 seconds with 2xx. Failures are retried with backoff for 24
  hours, after which the webhook is **disabled** until re-enabled in the Dashboard.
- At-least-once and unordered: `payment.captured` can arrive before `payment.authorized`.
- After rotating the secret, retries of older events still verify with the old secret.
- Separate from webhooks, verify the **Checkout callback**:
  `HMAC_SHA256(order_id + "|" + razorpay_payment_id, key_secret)` must equal
  `razorpay_signature`, using the `order_id` stored on **your** server.

## PayPal

Docs: <https://developer.paypal.com/api/rest/webhooks/rest/>

- Headers: `paypal-transmission-id`, `paypal-transmission-time`,
  `paypal-transmission-sig` (base64), `paypal-cert-url`.
- Self-verification (PayPal's preferred option): build
  `transmission_id|transmission_time|webhook_id|crc32(raw_body as decimal)`,
  download and cache the certificate from `paypal-cert-url` (only accept a
  PayPal domain), and verify the RSA-SHA256 signature. Alternatively post the
  event back unchanged to `POST /v1/notifications/verify-webhook-signature`.
- PayPal retries up to 25 times over 3 days.

## Adyen

Docs: <https://docs.adyen.com/development-resources/webhooks/secure-webhooks/verify-hmac-signatures>

- Standard notifications: `additionalData.hmacSignature` = base64 HMAC-SHA256
  (hex-decoded key) of
  `pspReference:originalReference:merchantAccountCode:merchantReference:value:currency:eventCode:success`.
- Respond within 10 seconds. Newer webhooks accept any 2xx (202 with empty body
  recommended); older ones still expect the body `[accepted]` until migrated.

## Debugging a signature failure

```bash
python ${CLAUDE_SKILL_DIR}/scripts/verify_webhook.py stripe \
    --body raw_body.json --header "t=...,v1=..." --secret whsec_test_...
python ${CLAUDE_SKILL_DIR}/scripts/verify_webhook.py razorpay \
    --body raw_body.json --header "<X-Razorpay-Signature>" --secret <webhook_secret>
python ${CLAUDE_SKILL_DIR}/scripts/verify_webhook.py stripe --body raw_body.json --secret whsec_test --sign
```

It explains the failure (wrong secret, modified body, stale timestamp, v0-only
header). Save the body **exactly** as received (bytes, no pretty-printing).
Use test-mode secrets; never paste live secrets into chats or logs.

## Review checklist

- [ ] Signature verified on the raw body before anything else; constant-time compare.
- [ ] Timestamp tolerance enforced (Stripe), certificate domain checked (PayPal).
- [ ] Secrets from environment/secret manager; separate test and live secrets.
- [ ] Event id stored with a unique constraint; duplicates return 2xx and do nothing.
- [ ] Handler returns 2xx fast; heavy work runs in a queue with retries.
- [ ] State changes are idempotent and order-independent (re-fetch the object;
      ignore transitions that move backwards).
- [ ] Unknown event types acknowledged and ignored, not errored.
- [ ] No secrets, card data or full payloads with personal data in logs.
- [ ] Monitoring on webhook failures (a disabled Razorpay webhook silently stops fulfilment).
- [ ] A reconciliation job catches anything webhooks missed (see `reconciliation`).
