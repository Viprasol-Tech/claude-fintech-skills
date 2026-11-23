# KYC/AML jurisdiction reference

Checked against official sources in **November 2026**. Thresholds, deadlines and
lists change; re-check each source before relying on it. Not legal advice.

## United States (Bank Secrecy Act / FinCEN, OFAC)

| Item | Rule | Source |
|---|---|---|
| Currency Transaction Report | Cash over **$10,000** per business day, aggregated | 31 CFR 1010.311/.313; <https://www.fincen.gov> |
| Geographic Targeting Order | Reissued 2 Sep 2026: MSBs in listed south-west border ZIP codes file CTRs for cash from $1,000 to $10,000 - fetch the current ZIP list | <https://www.fincen.gov/news/news-releases/fincen-issues-modified-southwest-border-geographic-targeting-order> |
| SAR - money services businesses | **$2,000** or more; file within **30 days** of detection | <https://www.fincen.gov/money-services-business-msb-suspicious-activity-reporting> |
| SAR - banks | **$5,000** or more; 30 calendar days (up to 60 if no suspect identified) | <https://www.fincen.gov/system/files/shared/report_reference.pdf> |
| BSA record retention | **5 years** | 31 CFR 1010.430 |
| Customer Identification Program (banks) | Name, date of birth, address, ID number (TIN for US persons) before account opening | 31 CFR 1020.220 |
| Beneficial ownership (CDD) | Each **25%+** owner plus one person with significant control. FIN-2026-R001 (Feb 2026): verify at first account opening, then only when information is in doubt or risk requires. A proposed rule (17 Nov 2026) would codify this - pending. | <https://fincen.gov/resources/statutes-and-regulations/cdd-final-rule> |
| MSB registration | FinCEN Form 107 within **180 days** of starting; renew every **2 years** | <https://www.fincen.gov/resources/money-services-business-msb-registration> |
| Travel Rule | **$3,000** (31 CFR 1010.410(f)); the proposal to lower it to $250 was withdrawn in November 2026 | <https://www.federalregister.gov/documents/2026/11/09/2026-22809/> |
| OFAC sanctions | Strict liability; the **50% rule** (aggregate ownership by blocked persons blocks the entity) | <https://ofac.treasury.gov/faqs/topic/1521> |
| OFAC lists | SDN and Consolidated lists from the Sanctions List Service; updated without a fixed schedule | <https://sanctionslist.ofac.treas.gov/Home/index.html> |
| OFAC record retention | **10 years** (effective 21 Mar 2025) | <https://ofac.treasury.gov/recent-actions/20250320> |

OFAC's own search uses fuzzy logic on names (character, string and phonetic
matching) and exact matching on ID numbers and crypto addresses
(<https://ofac.treasury.gov/faqs/246>). Resolve hits with date of birth,
nationality, ID numbers and address; most hits are false positives.

## European Union

| Item | Rule | Source |
|---|---|---|
| New AML package | AMLR (Reg. 2024/1624) applies mainly from **10 July 2027**; AMLD6 (Dir. 2024/1640) transposition by 10 July 2027; Directive 2015/849 repealed from that date | <https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32024R1624> |
| AMLA | EU AML Authority in Frankfurt, operational since 2025; direct supervision of up to 40 high-risk groups from 2028 | <https://www.amla.europa.eu/about-amla_en> |
| Crypto Travel Rule | Transfer of Funds Regulation 2023/1113 from **30 Dec 2024**: originator/beneficiary data on every crypto transfer involving a CASP, no minimum; for transfers over **EUR 1,000** to/from a self-hosted wallet, verify the customer owns or controls it | <https://eur-lex.europa.eu/eli/reg/2023/1113/oj/eng> |

## India (PMLA, RBI, FIU-IND)

| Item | Rule | Source |
|---|---|---|
| KYC rules | RBI **KYC Directions 2025** (28 Nov 2025), one set per entity type, replacing the 2016 Master Direction | <https://rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13141> |
| Video KYC (V-CIP) | Reject if the customer is being prompted; store V-CIP data and recordings on systems in India | KYC Directions, para 27 |
| CKYCR | Upload the KYC record to CKYCR within the deadline in the Directions (10 days of starting the relationship per para 65(2) when checked; confirm in the current text) | KYC Directions, para 65(2) |
| Record retention | Transactions: at least **5 years** from the transaction; identity records: at least 5 years after the relationship ends | KYC Directions, para 50 |
| Cash Transaction Report | Cash above **INR 10 lakh** (including connected series within a month), by the 15th of the next month | <https://fiuindia.gov.in/pdfs/quicklinks/Reporting_Format.pdf> |
| Suspicious Transaction Report | Within **7 working days** of concluding the transaction is suspicious | PML Rules, Rule 8 |

## United Kingdom

| Item | Rule | Source |
|---|---|---|
| Regulations | MLR 2017, amended by SI 2026/621 (mostly in force 30 June 2026) | <https://www.legislation.gov.uk/uksi/2026/621> |
| Suspicious Activity Reports | To the NCA (UKFIU) via the SAR Portal | <https://www.nationalcrimeagency.gov.uk/what-we-do/crime-threats/money-laundering-and-illicit-finance/suspicious-activity-reports> |
| Defence Against Money Laundering (DAML) | A request starts a **7 working day** notice period; a refusal starts a **31 day** moratorium. Do not proceed meanwhile - the system must be able to hold a transaction. | NCA |
| Crypto Travel Rule | In force since 1 Sep 2023 | <https://www.fca.org.uk/news/statements/fca-sets-out-expectations-uk-cryptoasset-businesses-complying-travel-rule> |

## FATF

- Key Recommendations: R.1 risk-based approach, R.12 politically exposed
  persons, R.15 virtual assets, R.16 wire transfers (revised June 2025, with
  standard data for cross-border payments above USD/EUR 1,000; compliance
  expected by end-2030).
- Black and grey lists change at each plenary (three times a year). As of
  30 Oct 2026 the "call for action" list is DPRK, Iran and Myanmar. Load the
  lists from <https://www.fatf-gafi.org/en/countries/black-and-grey-lists.html>;
  never hard-code countries.
