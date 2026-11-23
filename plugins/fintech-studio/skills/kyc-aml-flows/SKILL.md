---
name: kyc-aml-flows
description: Engineering checklist for KYC and AML features in fintech, crypto and payments apps - customer identity verification and tiers, beneficial ownership, sanctions screening (OFAC SDN, 50 percent rule, fuzzy matching, re-screening on list updates), PEP and adverse-media checks, transaction monitoring rules, alert case management with four-eyes review, SAR/STR deadlines, Travel Rule data, record retention by jurisdiction (US, EU, India, UK) and GDPR conflicts. Use when designing onboarding, screening or monitoring systems, choosing a KYC vendor, or reviewing compliance-related code. Engineering guidance, not legal advice.
---

# KYC / AML flows for engineers

Compliance teams decide the policy; engineers decide whether the system can
prove it was followed. Build for **evidence**: every decision reproducible from
stored inputs, rule versions and list versions. Jurisdiction facts with sources
and dates are in [reference.md](reference.md). This is engineering guidance,
not legal advice: confirm requirements with compliance counsel for your licence
and markets.

## Onboarding (KYC / CDD)

- Collect the identity data your regime requires (in the US for banks: name,
  date of birth, address, ID number), verify it through a documented method
  (document + liveness, database checks, video KYC where required), and store
  **what was checked, by which vendor, with what result and when**.
- Risk tiers: allow limited features at low assurance and raise limits only as
  verification completes. Encode tiers as data (limits per tier), not scattered `if`s.
- Businesses: capture beneficial owners (US: each 25%+ owner plus one control
  person) and the evidence for each.
- Screen at onboarding against sanctions lists, politically exposed persons
  and adverse media **before** the account can transact.
- Handle "pending" as a real state: the account exists but cannot move money.

## Sanctions screening

- Use the official lists (OFAC SDN and Consolidated lists; EU, UK and UN lists
  for those markets) or a vendor that cites them, and record the **list version**
  used for every check.
- Re-screen the **whole customer base** whenever a list changes, not only new sign-ups.
- Fuzzy-match names (transliteration, spacing, punctuation, word order);
  exact-match ID numbers and crypto addresses. Tune thresholds with compliance,
  and keep the tuning history.
- Apply OFAC's 50% rule for entities: aggregate ownership by blocked persons.
- A potential match blocks or holds the action until a human resolves it with a
  recorded reason. OFAC liability is strict: "the vendor missed it" is no defence.
- Screen payment counterparties too (beneficiaries, wallet addresses), not only customers.

## Transaction monitoring

- Rules as versioned configuration: thresholds, velocity (count/amount per
  window), structuring patterns (many amounts just under a reporting threshold),
  rapid in-and-out movement, high-risk geographies, new-account spikes.
- Load high-risk jurisdiction lists (FATF black/grey lists) from their source
  on each update; never hard-code countries.
- Every alert stores the triggering transactions, the rule id **and version**,
  and the inputs, so the decision can be replayed later.
- Scores from ML models need explainability: store the features and reasons,
  model version and validation records.

## Case management

```text
alert -> triage -> investigation -> decision -> (report filed | closed with reason)
```

- Each transition records who, when and why. Closures, report decisions,
  list-match overrides and rule changes need a **second reviewer** (four eyes).
- Track reporting deadlines from the **detection timestamp**: for example 30
  days for US SARs, 7 working days for India STRs, and the UK DAML notice period
  (7 working days, during which the transaction must stay on hold).
- **No tipping off:** customers must never see alert or report status, directly
  or through error messages, support tools or account behaviour that reveals it.

## Records and audit trail

- Append-only, tamper-evident storage (hash chain or WORM) for KYC evidence,
  screening results, alerts, cases and reports.
- Retention differs by regime, so store the clock-start date per record type:
  BSA records 5 years, OFAC records 10 years (since March 2025), India identity
  records 5 years after the relationship ends.
- GDPR and similar laws: data minimisation and erasure requests yield to legal
  retention duties during the retention period (Art. 17(3)(b)); delete on
  schedule afterwards. Automated adverse decisions may engage Art. 22 - keep a
  human in the loop.

## Travel Rule (payments and crypto)

Originator and beneficiary data must travel with transfers above the
applicable thresholds: $3,000 in the US; every crypto transfer involving a
crypto-asset service provider in the EU (no minimum), plus ownership checks for
self-hosted wallets over EUR 1,000. Design message formats and storage for it
from the start.

## Review checklist

- [ ] Account states include pending / restricted; nothing transacts before
      required checks pass.
- [ ] Every verification, screening and monitoring decision stores inputs,
      vendor/rule/list versions and timestamps.
- [ ] Full re-screen on every sanctions list update.
- [ ] Alerts become cases with owners, deadlines, four-eyes approval and reasons.
- [ ] Reporting deadlines computed from detection time and alerted before expiry.
- [ ] No tipping off anywhere in the product or support tooling.
- [ ] Audit trail is append-only; retention per regime is configured and enforced.
- [ ] Thresholds, rules and country lists are versioned configuration loaded
      from their sources.
- [ ] Personal data minimised, encrypted, access-logged and deleted on schedule.
