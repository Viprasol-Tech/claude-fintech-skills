#!/usr/bin/env python3
"""Exact money arithmetic: minor units, rounding, allocation, FX, fees and tax.

Part of claude-fintech-skills by Viprasol Tech Private Limited.

Every amount is a Decimal or an integer count of minor units (cents, paise,
fils). Floats are never used. Standard library only.
Run ``python money.py --self-test`` to check it.

Examples:
  python money.py to-minor 19.99 USD             # 1999
  python money.py to-minor 1500 JPY              # 1500 (JPY has no minor unit)
  python money.py from-minor 12345 KWD           # 12.345
  python money.py allocate 10000 USD 1 1 1       # 3334 3333 3333 (sums to 10000)
  python money.py convert 10000 USD INR 83.4517  # 834517
  python money.py fee 10000 USD --pct 2.9 --fixed 30
  python money.py split-tax 11800 INR --rate 18 --inclusive
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Decimal, DecimalException, InvalidOperation

# ISO 4217 minor units for currencies that do not use 2. Everything in
# TWO_DECIMAL uses 2. Unknown codes are rejected (pass --exponent CODE=N).
MINOR_UNITS: dict[str, int] = {
    # 0 decimals
    "BIF": 0, "CLP": 0, "DJF": 0, "GNF": 0, "ISK": 0, "JPY": 0, "KMF": 0, "KRW": 0,
    "PYG": 0, "RWF": 0, "UGX": 0, "UYI": 0, "VND": 0, "VUV": 0, "XAF": 0, "XOF": 0, "XPF": 0,
    # 3 decimals
    "BHD": 3, "IQD": 3, "JOD": 3, "KWD": 3, "LYD": 3, "OMR": 3, "TND": 3,
    # 4 decimals
    "CLF": 4, "UYW": 4,
}

TWO_DECIMAL = frozenset("""
AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BGN BMD BND BOB BOV BRL BSD BTN BWP BYN BZD
CAD CDF CHE CHF CHW CNY COP COU CRC CUP CVE CZK DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL
GHS GIP GMD GTQ GYD HKD HNL HTG HUF IDR ILS INR IRR JMD KES KGS KHR KPW KYD KZT LAK LBP LKR
LRD LSL MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD
PAB PEN PGK PHP PKR PLN QAR RON RSD RUB SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC
SYP SZL THB TJS TMT TOP TRY TTD TWD TZS UAH USD USN UYU UZS VED VES WST XCD XCG YER ZAR ZMW ZWG
""".split())

# Plain digits, or digits grouped with commas in threes; '.' is the only decimal
# separator. "1,50" (a European decimal comma) is rejected, not read as 150.
_AMOUNT_RE = re.compile(r"^[-+]?(\d+|\d{1,3}(,\d{3})+)(\.\d+)?$")

ROUNDING = {
    "half-even": ROUND_HALF_EVEN,  # banker's rounding: unbiased over many operations
    "half-up": ROUND_HALF_UP,      # what most people and many tax rules expect
    "up": ROUND_UP,                # away from zero, e.g. for fees you charge
    "down": ROUND_DOWN,            # toward zero, e.g. for amounts you pay out
}


def minor_units(currency: str) -> int:
    code = currency.upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(f"not an ISO 4217 code: {currency!r}")
    if code in MINOR_UNITS:
        return MINOR_UNITS[code]
    if code in TWO_DECIMAL:
        return 2
    raise ValueError(f"unknown currency {code}; pass --exponent {code}=N if it is valid")


def dec(value: str | int | Decimal) -> Decimal:
    if isinstance(value, float):
        raise TypeError("floats are not allowed for money; pass a string or Decimal")
    text = str(value).strip().replace(" ", "")
    if not isinstance(value, Decimal) and not _AMOUNT_RE.match(text):
        raise ValueError(f"not an unambiguous amount: {value!r} (use '.' for decimals, ',' only for thousands)")
    try:
        d = Decimal(text.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value!r}") from exc
    if not d.is_finite():
        raise ValueError(f"not a finite number: {value!r}")
    return d


def round_money(amount: Decimal, currency: str, mode: str = "half-even") -> Decimal:
    exp = Decimal(1).scaleb(-minor_units(currency))
    return amount.quantize(exp, rounding=ROUNDING[mode])


def to_minor(amount: str | Decimal, currency: str, strict: bool = True, mode: str = "half-even") -> int:
    """Major units -> integer minor units. strict=True rejects extra precision instead of rounding."""
    d = dec(amount)
    places = minor_units(currency)
    if strict and d != d.quantize(Decimal(1).scaleb(-places)):
        raise ValueError(f"{amount} has more than {places} decimal places for {currency.upper()}")
    return int(round_money(d, currency, mode).scaleb(places))


def from_minor(minor: int, currency: str) -> Decimal:
    places = minor_units(currency)
    return Decimal(minor).scaleb(-places).quantize(Decimal(1).scaleb(-places))


def allocate(total_minor: int, ratios: list[Decimal]) -> list[int]:
    """Split total_minor by ratios so the parts always sum to the total (largest remainder)."""
    if not ratios or any(r < 0 for r in ratios) or sum(ratios) == 0:
        raise ValueError("ratios must be non-negative and not all zero")
    weight = sum(ratios)
    sign = -1 if total_minor < 0 else 1
    total = abs(total_minor)
    exact = [Decimal(total) * r / weight for r in ratios]
    parts = [int(x.to_integral_value(rounding=ROUND_DOWN)) for x in exact]
    leftover = total - sum(parts)
    order = sorted(range(len(ratios)), key=lambda i: (-(exact[i] - parts[i]), i))
    for i in order[:leftover]:
        parts[i] += 1
    return [sign * p for p in parts]


def convert(amount_minor: int, src: str, dst: str, rate: str | Decimal, mode: str = "half-even") -> int:
    """Convert minor units of src into minor units of dst at `rate` (dst per 1 src)."""
    r = dec(rate)
    if r <= 0:
        raise ValueError("rate must be positive")
    major = from_minor(amount_minor, src) * r
    return to_minor(round_money(major, dst, mode), dst)


def fee(amount_minor: int, currency: str, pct: str | Decimal = "0", fixed_minor: int = 0, mode: str = "half-up") -> int:
    """Percentage + fixed fee in minor units, e.g. 2.9% + 30. Fees on refunds are a separate policy."""
    if amount_minor < 0:
        raise ValueError("amount must be non-negative")
    raw = Decimal(amount_minor) * dec(pct) / Decimal(100)
    return int(raw.to_integral_value(rounding=ROUNDING[mode])) + fixed_minor


def split_tax(amount_minor: int, currency: str, rate_pct: str | Decimal, inclusive: bool,
              mode: str = "half-up") -> dict[str, int]:
    """Net / tax / gross in minor units. inclusive=True means amount already contains the tax."""
    rate = dec(rate_pct) / Decimal(100)
    if rate <= -1:
        raise ValueError("tax rate must be above -100%")
    if inclusive:
        gross = amount_minor
        net = int((Decimal(gross) / (1 + rate)).to_integral_value(rounding=ROUNDING[mode]))
        tax = gross - net  # derive tax by subtraction so net + tax == gross exactly
    else:
        net = amount_minor
        tax = int((Decimal(net) * rate).to_integral_value(rounding=ROUNDING[mode]))
        gross = net + tax
    return {"net": net, "tax": tax, "gross": gross}


def _self_test() -> None:
    assert to_minor("19.99", "USD") == 1999 and to_minor("1500", "JPY") == 1500
    assert to_minor("12.345", "KWD") == 12345 and to_minor("0.0001", "CLF") == 1
    assert str(from_minor(12345, "KWD")) == "12.345" and str(from_minor(5, "USD")) == "0.05"
    assert str(from_minor(1500, "JPY")) == "1500"
    for bad in [("19.999", "USD"), ("1.5", "JPY")]:
        try:
            to_minor(*bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} should be rejected")
    for bad_amount in ["1,50", "1.234,56", "12,34,567", "1e3", "abc"]:
        try:
            to_minor(bad_amount, "EUR")
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad_amount!r} must be rejected as ambiguous")
    assert to_minor("1,234.56", "USD") == 123456
    try:
        minor_units("XYZ")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown currency must be rejected")
    for bad_call in (lambda: fee(-1000, "USD", "2.9", 30), lambda: split_tax(100, "USD", "-100", True)):
        try:
            bad_call()
        except ValueError:
            pass
        else:
            raise AssertionError("must reject")
    assert to_minor("19.995", "USD", strict=False) == 2000          # half-even: 1999.5 -> 2000
    assert to_minor("19.985", "USD", strict=False) == 1998          # half-even: 1998.5 -> 1998
    assert to_minor("19.985", "USD", strict=False, mode="half-up") == 1999
    try:
        dec(0.1)  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("floats must be refused")
    parts = allocate(10000, [Decimal(1)] * 3)
    assert parts == [3334, 3333, 3333] and sum(parts) == 10000
    assert allocate(-100, [Decimal(1), Decimal(1), Decimal(1)]) == [-34, -33, -33]
    assert sum(allocate(99999, [Decimal("0.7"), Decimal("0.2"), Decimal("0.1")])) == 99999
    assert convert(10000, "USD", "INR", "83.4517") == 834517
    assert convert(100000, "JPY", "USD", "0.006671") == 66710
    assert fee(10000, "USD", "2.9", 30) == 320
    assert fee(1234, "USD", "2.9", 30) == 66                         # 35.786 -> 36 + 30
    t = split_tax(11800, "INR", "18", inclusive=True)
    assert t == {"net": 10000, "tax": 1800, "gross": 11800}, t
    e = split_tax(9999, "USD", "8.875", inclusive=False)
    assert e["net"] + e["tax"] == e["gross"] and e["tax"] == 887
    print("money self-test passed")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exact money arithmetic (no floats)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--exponent", action="append", default=[], metavar="CODE=N",
                    help="Minor-unit exponent for a currency not in the built-in list")
    ap.add_argument("--rounding", choices=list(ROUNDING), default=None,
                    help="Rounding mode (default: half-even, or half-up for fee and tax)")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("to-minor", help="Major units to integer minor units")
    p.add_argument("amount"); p.add_argument("currency")
    p.add_argument("--round", action="store_true", help="Round extra precision instead of rejecting it")
    p = sub.add_parser("from-minor", help="Integer minor units to major units")
    p.add_argument("minor", type=int); p.add_argument("currency")
    p = sub.add_parser("allocate", help="Split minor units by ratios without losing a unit")
    p.add_argument("total", type=int); p.add_argument("currency"); p.add_argument("ratios", nargs="+")
    p = sub.add_parser("convert", help="Convert minor units between currencies")
    p.add_argument("minor", type=int); p.add_argument("src"); p.add_argument("dst")
    p.add_argument("rate", help="Units of dst per 1 unit of src")
    p = sub.add_parser("fee", help="Percentage + fixed fee")
    p.add_argument("minor", type=int); p.add_argument("currency")
    p.add_argument("--pct", default="0"); p.add_argument("--fixed", type=int, default=0)
    p = sub.add_parser("split-tax", help="Net / tax / gross")
    p.add_argument("minor", type=int); p.add_argument("currency")
    p.add_argument("--rate", required=True, help="Tax rate in percent")
    p.add_argument("--inclusive", action="store_true", help="Amount already includes tax")
    args = ap.parse_args(argv)
    if args.self_test:
        _self_test()
        return 0
    mode = args.rounding
    try:
        for item in args.exponent:
            code, _, n = item.partition("=")
            if not (len(code) == 3 and code.isalpha() and n.isdigit()):
                raise ValueError(f"--exponent expects CODE=N, got {item!r}")
            MINOR_UNITS[code.upper()] = int(n)
        if args.cmd == "to-minor":
            out: object = to_minor(args.amount, args.currency, strict=not args.round, mode=mode or "half-even")
        elif args.cmd == "from-minor":
            out = str(from_minor(args.minor, args.currency))
        elif args.cmd == "allocate":
            out = allocate(args.total, [dec(r) for r in args.ratios])
        elif args.cmd == "convert":
            out = convert(args.minor, args.src, args.dst, args.rate, mode or "half-even")
        elif args.cmd == "fee":
            out = fee(args.minor, args.currency, args.pct, args.fixed, mode or "half-up")
        elif args.cmd == "split-tax":
            out = split_tax(args.minor, args.currency, args.rate, args.inclusive, mode or "half-up")
        else:
            ap.print_help()
            return 2
    except (ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except DecimalException:
        print("error: number too large or invalid for exact decimal arithmetic", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(out))
    elif isinstance(out, list):
        print(" ".join(str(x) for x in out))
    elif isinstance(out, dict):
        for k, v in out.items():
            print(f"{k:<6}{v}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
