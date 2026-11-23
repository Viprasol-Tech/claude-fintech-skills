# Contributing

Thanks for helping make money-handling code safer. Fixes, new skills, better
checklists and corrections are all welcome.

## Ways to help

- **Fix a fact.** Payment APIs, PCI DSS and AML rules change. If a rule, limit
  or header is out of date, open a PR with a link to the official source.
- **Improve a skill.** Each skill is a folder in `plugins/fintech-studio/skills/`
  with a `SKILL.md` (YAML frontmatter `name` + `description`, then instructions).
- **Add a skill.** Same layout. Keep `SKILL.md` under 500 lines; put long
  reference material in a separate file linked from it.
- **Improve the scripts** in `money-math/scripts`, `reconciliation/scripts` and `webhook-security/scripts`.
  They must stay standard-library only and keep their `--self-test` passing.

## Before you open a PR

```bash
python tests/validate_repo.py
python plugins/fintech-studio/skills/money-math/scripts/money.py --self-test
python plugins/fintech-studio/skills/reconciliation/scripts/recon.py --self-test
python plugins/fintech-studio/skills/webhook-security/scripts/verify_webhook.py --self-test
```

Code samples must run as written, use test-mode keys only, and treat amounts as
integers in minor units or decimals, never floats.

## Ground rules

- Accuracy over volume: cite official docs for platform facts.
- Compliance content (PCI, KYC/AML) is engineering guidance, not legal advice; cite the regulator or standard.
- Never include real API keys, account numbers or personal data.
