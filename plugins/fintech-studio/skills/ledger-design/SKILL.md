---
name: ledger-design
description: Design and review double-entry ledgers for fintech products - wallets, marketplaces, payouts, lending, loyalty points, prepaid balances - with immutable journal entries, balanced postings, account types and normal balances, idempotent writes, pending vs. posted states, reversals instead of edits, multi-currency, and balance queries that stay correct under concurrency. Includes a Postgres schema. Use when building wallet balances, user credits, escrow, payouts or any feature that moves money between accounts, or when reviewing balance code that updates a number in place.
---

# Double-entry ledger design

If a balance is a column you `UPDATE`, it will eventually be wrong and you will
not be able to say why. A ledger records every movement as an immutable,
balanced entry; balances are derived from it. Use this skill to design one or
to review existing balance code.

## Core rules

1. **Every entry balances.** A journal entry has two or more postings whose
   signed amounts sum to exactly zero, per currency.
2. **Append-only.** Never update or delete a posted entry. Correct mistakes with
   a reversing entry plus a new correct entry, linked to the original.
3. **Integers in minor units**, with the currency on every posting (see the
   `money-math` skill). No floats anywhere.
4. **Idempotent writes.** Every entry carries an idempotency key from the
   business event (`payment:pi_123:captured`); a unique constraint makes a retry
   a no-op instead of a double credit.
5. **Balances are derived** from postings. A cached balance is allowed for
   speed, but it is updated in the same transaction as the postings and can be
   rebuilt from them at any time.
6. **Time has two meanings:** `effective_at` (when it happened economically)
   and `created_at` (when it was recorded). Reports use the first; audits need both.

## Account model

| Type | Normal balance | Examples |
|---|---|---|
| Asset | debit | cash at bank, funds held at Stripe, receivables, loans issued |
| Liability | credit | customer wallet balances, merchant payables, deposits held |
| Equity | credit | owner capital, retained earnings |
| Revenue | credit | platform fees, interest income |
| Expense | debit | payment processing fees, refunds absorbed, chargeback losses |

Customer money you hold is a **liability** to you, not revenue. A marketplace
that collects 100 and owes the seller 90 has 90 of liability and 10 of revenue.

Use one sign convention throughout: for example **debits positive, credits
negative**, so every entry sums to zero and an account's balance is the sum
of its postings (flip the sign for credit-normal accounts when displaying).

## Schema (PostgreSQL)

```sql
create table ledger_accounts (
  id            bigserial primary key,
  code          text not null unique,              -- 'liability:wallet:user_42'
  type          text not null check (type in ('asset','liability','equity','revenue','expense')),
  currency      char(3) not null,
  allow_negative boolean not null default false,
  created_at    timestamptz not null default now()
);

create table ledger_entries (
  id              bigserial primary key,
  idempotency_key text not null unique,            -- retry-safe
  description     text not null,
  effective_at    timestamptz not null,
  created_at      timestamptz not null default now(),
  reverses_entry  bigint references ledger_entries(id),
  metadata        jsonb not null default '{}'
);

create table ledger_postings (
  id          bigserial primary key,
  entry_id    bigint not null references ledger_entries(id),
  account_id  bigint not null references ledger_accounts(id),
  amount      bigint not null check (amount <> 0),  -- minor units; debit > 0, credit < 0
  currency    char(3) not null
);
create index on ledger_postings (account_id, entry_id);

-- Append-only: block updates and deletes for the application role.
-- The tables must be OWNED by a different role (a migration role): owners
-- bypass grants, so revoking from the owner does nothing.
revoke update, delete on ledger_entries, ledger_postings from app_role;
```

Enforce "entry sums to zero per currency" in the single function that writes
entries (and optionally a deferred constraint trigger), and check that each
posting's currency equals its account's currency.

## Writing an entry safely

```sql
begin;
-- 1. lock the accounts in a fixed order (by id) to avoid deadlocks
select id from ledger_accounts where id = any($account_ids) order by id for update;
-- 2. insert the entry. On an idempotency conflict this returns NO row.
insert into ledger_entries (idempotency_key, description, effective_at)
values ($key, $desc, $at)
on conflict (idempotency_key) do nothing
returning id;
-- 2b. no row came back = this event was already recorded: fetch and return it,
--     and write NO postings.
select id from ledger_entries where idempotency_key = $key;
-- 3. new entry: insert postings, verify sum(amount) = 0 per currency, and verify
--    no account with allow_negative = false ends below zero IN ITS NORMAL
--    DIRECTION (see the balance query below)
commit;
```

Because credits are negative, a liability, equity or revenue account normally
sums **below** zero (a wallet top-up posts -100 to the wallet). Check balances
in the account's normal direction:

```sql
select case when a.type in ('asset','expense') then coalesce(sum(p.amount), 0)
            else -coalesce(sum(p.amount), 0) end as balance
from ledger_accounts a
left join ledger_postings p on p.account_id = a.id
where a.id = $1
group by a.type;
-- reject the entry if balance < 0 and allow_negative = false
```

A user's wallet "going negative" means this normal-direction balance drops
below zero, i.e. they spent more than they had.
For hot accounts, keep a `balances` row updated inside the same transaction, and
run a nightly job that recomputes it from postings and alerts on any difference.

## Common flows

| Event | Debit | Credit |
|---|---|---|
| Customer tops up wallet 100 via card | Asset: funds at processor 100 | Liability: user wallet 100 |
| Processor fee 3 on that top-up | Expense: processing fees 3 | Asset: funds at processor 3 |
| Marketplace sale 100, 10% fee | Liability: buyer wallet 100 | Liability: seller payable 90, Revenue: platform fee 10 |
| Payout 90 to seller's bank | Liability: seller payable 90 | Asset: funds at processor 90 |
| Refund 100 to card | Liability: user wallet 100 | Asset: funds at processor 100 |

Card payments are **pending** until settled. Either model pending as separate
accounts (`asset:processor:pending` -> `asset:processor:available`) or as an
entry status; never let users spend money that is only authorised.

## Review checklist

- [ ] No `UPDATE accounts SET balance = balance + x` outside a ledger write.
- [ ] Every money movement creates a balanced entry; nothing writes postings directly.
- [ ] Idempotency key with a unique constraint on every entry.
- [ ] Integers in minor units; currency stored per posting; no cross-currency entry
      without explicit FX accounts (one entry per currency, each summing to zero).
- [ ] No updates or deletes of posted entries; reversals are linked.
- [ ] Concurrency: row locks in a consistent order or serializable isolation;
      negative-balance checks inside the same transaction.
- [ ] Pending vs. available funds separated.
- [ ] Daily reconciliation of ledger balances against the processor and the bank
      (see the `reconciliation` skill).
- [ ] An audit trail of who or what created each entry.

Accounting treatment (revenue recognition, tax) depends on jurisdiction; have
an accountant review the chart of accounts for production use.
