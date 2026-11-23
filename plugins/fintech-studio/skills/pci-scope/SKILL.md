---
name: pci-scope
description: Work out and shrink PCI DSS v4.0.1 scope for a payment integration - which self-assessment questionnaire applies (SAQ A, A-EP, C-VT, D) for redirects, iframes and hosted fields vs. merchant-built or direct-post forms, the 2025 SAQ A script-eligibility rule, what card data may never be stored (CVV, full track, PIN), PAN masking (BIN + last four), tokenization, payment-page script controls (6.4.3, 11.6.1), quarterly ASV scans and MFA - and catch the developer mistakes that pull systems into scope, such as card data in logs, error trackers or session replay. Use when choosing a checkout integration, preparing for a PCI assessment, reviewing payment pages or logging, or answering "are we PCI compliant?".
---

# PCI DSS scope for developers

The cheapest PCI programme is the one where card data never touches your
systems. Use this skill to pick an integration that keeps scope small, and to
find the code that quietly makes it big. This is engineering guidance, not a
compliance determination: your acquirer decides which SAQ you file, and a QSA
or the acquirer has the final word.

## Status (late 2026)

PCI DSS **v4.0.1** (June 2024) is the only active version; v4.0 retired on
31 December 2024. The future-dated requirements became mandatory on
**31 March 2025**. Source: <https://blog.pcisecuritystandards.org/just-published-pci-dss-v4-0-1>.

## Which SAQ?

| Integration | Typical SAQ | Why |
|---|---|---|
| Full redirect to the provider's hosted payment page (Stripe Checkout, PayPal, Razorpay hosted checkout) | **A** | Every payment-page element comes from the PCI-compliant provider |
| Provider iframe / hosted fields embedded in your page (Stripe Elements, Adyen Drop-in/Components, Braintree Hosted Fields) | **A**, if you meet the script criterion below | Card fields are served by the provider inside your page |
| Your page builds the form or posts card data straight to the provider (direct post, JS-built fields on your origin, Stripe.js v2-style own form) | **A-EP** | Your site controls the payment page, so it becomes part of the cardholder data environment |
| Staff type cards into the provider's browser virtual terminal | **C-VT** | Manual entry, no electronic storage |
| Card numbers reach your servers or API (raw card APIs, card numbers in your DB) | **D** | You store, process or transmit PAN |
| You are a service provider (others' card data passes through you) | **SAQ D for service providers** (or a ROC) | The only SAQ for service providers |

Stripe's own mapping, for example: Checkout and Elements -> A; Stripe.js v2
own form -> A-EP; Dashboard manual entry -> C-VT; raw card data to the API -> D
(<https://stripe.com/guides/pci-compliance>). SAQ A also requires **quarterly
external ASV scans** (11.3.2) under v4.x, for redirect and iframe merchants alike
(<https://www.pcisecuritystandards.org/faqs/1604/>).

### The 2025 SAQ A script rule

Since 31 March 2025, SAQ A no longer lists requirements 6.4.3 and 11.6.1, but
adds an eligibility criterion: the merchant must confirm its site is **not
susceptible to attacks from scripts** that could affect its e-commerce systems
(<https://blog.pcisecuritystandards.org/important-updates-announced-for-merchants-validating-to-self-assessment-questionnaire-a>).
Per SSC FAQ 1588 this applies to pages that **embed** a provider's form (iframe),
not to pure redirects. You meet it either by applying controls like those in
6.4.3 and 11.6.1 yourself, or by getting confirmation from your PCI-compliant
provider that its embedded solution, implemented as instructed, protects the
page from script attacks. The underlying requirements still exist; acquirers
and brands set validation rules.

## Data you may never store

- **Sensitive authentication data (SAD)** - full track data, CVV2/CVC2/CID,
  PIN or PIN block - must not be retained after authorisation, **even if
  encrypted** (3.3.1). That includes logs, queues, analytics and call recordings.
- **PAN at rest** must be unreadable (3.5.1): truncation, index tokens, strong
  cryptography, or a keyed cryptographic hash of the whole PAN (keyed hashes are
  required for hashes created after 31 March 2025). Do not store a hash and a
  truncated form of the same PAN together.
- **Display:** show no more than the **BIN and last four digits** (3.4.1) unless
  a documented business need justifies more. Masking is display-only; a full
  PAN behind a masked screen is still stored PAN.
- Provider tokens, card brand, last four and expiry returned by the provider are
  generally outside cardholder data scope (for example Stripe's guidance:
  <https://docs.stripe.com/security/guide>).

## Payment-page controls (A-EP, D, and the SAQ A script criterion)

- **6.4.3:** inventory every script that runs on the payment page (first-,
  third- and fourth-party), with a written justification, a way to confirm each
  is authorised, and a way to assure its integrity. In practice: a strict
  Content-Security-Policy (start in report-only), Subresource Integrity on
  static scripts, and CSP violation reporting.
- **11.6.1:** a change- and tamper-detection mechanism that alerts on
  unauthorised changes to the payment page's security-impacting HTTP headers and
  script contents as received by the browser, at least every seven days (or as
  set by a targeted risk analysis).
- **8.4.2:** MFA for all access into the cardholder data environment (FIDO2
  passkeys can satisfy it, per SSC FAQ 1595).
- **11.3.2:** quarterly external scans by an Approved Scanning Vendor.

## Scope leaks to hunt for in code

- [ ] Card numbers or CVV in **application logs**, request logging middleware,
      API gateway logs or debug dumps (search for `card`, `pan`, `cvv`, `cvc`,
      `number` in log statements and serializers).
- [ ] **Error trackers** (Sentry, Bugsnag, Datadog) capturing request bodies or
      form values on checkout pages - configure scrubbing or exclude those routes.
- [ ] **Session replay and analytics** (FullStory, Hotjar, LogRocket, GA)
      recording payment fields or running on the payment page at all.
- [ ] Tag managers injecting unreviewed scripts into checkout.
- [ ] Your own form fields named `card_number` posting to your server "just to
      forward it" - that is SAQ D.
- [ ] Card data in emails, support tickets, chat transcripts or CSV exports.
- [ ] Test card numbers mixed with real data in non-production databases.
- [ ] Backups or data warehouses copying tables that once held PAN.

## Merchant levels

Levels are set by the card brands and assigned by your acquirer. Roughly, Visa
Level 1 is over 6 million Visa transactions a year (annual Report on Compliance
by a QSA); Levels 2-4 usually file an SAQ. A breached merchant can be moved up a
level. Check your acquirer's requirements.

## Output when reviewing

```markdown
## Likely SAQ: <A | A-EP | C-VT | D> (confirm with your acquirer)
Why: <integration facts>

## Scope leaks found
| # | Where | Data | Fix |

## To stay at SAQ A
<concrete changes: switch to hosted fields, remove scripts from checkout, scrub logs>
```
