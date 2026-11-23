# Security policy

## Reporting a vulnerability

Please report security problems privately through
[GitHub security advisories](https://github.com/Viprasol-Tech/claude-fintech-skills/security/advisories/new)
or by email to [support@viprasol.com](mailto:support@viprasol.com). Do not open a public issue.
We aim to reply within 3 working days.

## Scope

- The bundled scripts (`money.py`, `recon.py`, `verify_webhook.py`): they read local CSV files or
  command-line values and print results. They make no network calls and run no
  shell commands.
- Skill instructions that could lead an assistant to weaken payment security:
  skipping webhook verification, logging card data, mishandling credentials.

## Keep secrets and card data out of chats

These skills never need your API keys, webhook secrets or real customer data.
Never paste live keys (`sk_live_...`, `rzp_live_...`), webhook secrets, card
numbers or personal data into an issue, pull request or chat. Use test-mode
keys and synthetic data. If a key has been exposed, roll it in your provider's
dashboard immediately.
