# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-23

### Added
- `fintech-studio` Claude Code plugin with 8 skills: `money-math`,
  `ledger-design`, `payments-integration`, `webhook-security`,
  `subscription-billing`, `reconciliation`, `pci-scope`, `kyc-aml-flows`.
- `money.py`: minor units per ISO 4217, rounding modes, remainder-safe
  allocation, FX conversion, fees and tax splits, with no floats.
- `recon.py`: one-to-one ledger vs. provider/bank matching by reference, then
  amount and date, with an exceptions report and a non-zero exit code for alerts.
- PostgreSQL double-entry ledger schema.
- Marketplace manifest, installers for Windows/macOS/Linux, and CI that
  validates every skill and runs the script self-tests.
