#!/usr/bin/env python3
"""Reconcile two transaction files: your ledger vs. a payment provider or bank export.

Part of claude-fintech-skills by Viprasol Tech Private Limited.

Matching runs in passes, each one-to-one:
  1. exact reference match (order id, charge id, UTR, invoice number)
  2. same amount (within --amount-tolerance) and date within --days, no reference needed
Anything left is reported as unmatched on its side. Reference matches whose
amounts differ are reported as amount mismatches.

Amounts are parsed as Decimal (never float). Standard library only.
Run ``python recon.py --self-test`` to check it.

Example:
  python recon.py ledger.csv stripe_payouts.csv \
      --left-amount amount --left-date created_at --left-ref order_id \
      --right-amount net --right-scale 0.01 --right-date available_on \
      --right-ref metadata_order_id \
      --days 3 --out recon_report.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

# Plain digits or comma-grouped thousands; '.' is the only decimal separator.
_AMOUNT_RE = re.compile(r"^-?(\d+|\d{1,3}(,\d{3})+)(\.\d+)?$")


@dataclass
class Txn:
    side: str
    row: int
    amount: Decimal
    day: date | None
    ref: str
    raw: dict[str, str] = field(repr=False)


def parse_amount(text: str) -> Decimal:
    t = text.strip()
    for sym in ("$", "₹", "€", "£", " "):
        t = t.replace(sym, "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if not _AMOUNT_RE.match(t):
        raise ValueError(f"not an unambiguous amount: {text!r} (use '.' for decimals, ',' only for thousands)")
    d = Decimal(t.replace(",", ""))
    return -d if neg else d


def parse_day(text: str, fmt: str | None) -> date | None:
    """ISO 8601 dates/times are detected (timezone offsets converted to UTC).
    Anything else, such as 05/11/2026, is ambiguous and needs --date-format."""
    t = text.strip()
    if not t:
        return None
    if fmt:
        return datetime.strptime(t, fmt).date()
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(t, "%Y/%m/%d").date()
        except ValueError:
            raise ValueError(
                f"date {text!r} is not ISO 8601; pass --date-format (e.g. %d/%m/%Y or %m/%d/%Y)"
            ) from None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.date()


def load(path: str, side: str, amount_col: str, date_col: str | None, ref_col: str | None,
         date_fmt: str | None, scale: Decimal) -> list[Txn]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        for c in (amount_col, date_col, ref_col):
            if c and c not in cols:
                raise ValueError(f"{path}: column {c!r} not found; columns are: {', '.join(cols)}")
        out = []
        for i, row in enumerate(reader, start=2):
            if not (row.get(amount_col) or "").strip():
                continue
            out.append(Txn(
                side=side,
                row=i,
                amount=parse_amount(row[amount_col]) * scale,
                day=parse_day(row.get(date_col) or "", date_fmt) if date_col else None,
                ref=(row.get(ref_col) or "").strip() if ref_col else "",
                raw=row,
            ))
        return out


def reconcile(left: list[Txn], right: list[Txn], amount_tol: Decimal = Decimal(0), days: int = 0) -> dict:
    matched: list[tuple[Txn, Txn, str]] = []
    mismatched: list[tuple[Txn, Txn]] = []
    used_r: set[int] = set()
    used_l: set[int] = set()

    by_ref: dict[str, list[int]] = {}
    for j, r in enumerate(right):
        if r.ref:
            by_ref.setdefault(r.ref, []).append(j)
    for i, lt in enumerate(left):
        if not lt.ref or lt.ref not in by_ref:
            continue
        cands = [j for j in by_ref[lt.ref] if j not in used_r]
        if not cands:
            continue
        j = min(cands, key=lambda k: abs(right[k].amount - lt.amount))
        used_l.add(i)
        used_r.add(j)
        if abs(right[j].amount - lt.amount) <= amount_tol:
            matched.append((lt, right[j], "reference"))
        else:
            mismatched.append((lt, right[j]))

    # Pass 2: amount + date proximity. Build every eligible pair, then assign
    # one-to-one starting from the closest dates (ties by file order).
    pairs = []
    for i, lt in enumerate(left):
        if i in used_l:
            continue
        for j, r in enumerate(right):
            if j in used_r or abs(r.amount - lt.amount) > amount_tol:
                continue
            if lt.day and r.day:
                gap = abs((r.day - lt.day).days)
                if gap > days:
                    continue
            else:
                gap = days + 1  # a missing date may match, but only after dated candidates
            pairs.append((gap, i, j))

    # Maximum one-to-one matching (Kuhn's augmenting paths). Candidates are tried
    # closest date first, so ties go to the nearest-dated transaction.
    # ponytail: O(V*E); fine for daily files, switch to Hopcroft-Karp for millions of rows.
    cands: dict[int, list[int]] = {}
    for _gap, i, j in sorted(pairs):
        cands.setdefault(i, []).append(j)
    owner: dict[int, int] = {}  # right index -> left index

    def augment(start: int) -> None:
        """Iterative augmenting-path search (no recursion limit on large files)."""
        seen: set[int] = set()
        parent: dict[int, tuple[int, int | None]] = {}  # right j -> (left i, previous right)
        stack: list[tuple[int, int | None]] = [(start, None)]
        while stack:
            i, via = stack.pop()
            for j in reversed(cands.get(i, [])):  # reversed: closest candidate popped first
                if j in seen:
                    continue
                seen.add(j)
                parent[j] = (i, via)
                if j not in owner:
                    while True:  # walk back, flipping the path
                        li, prev = parent[j]
                        owner[j] = li
                        if prev is None:
                            return
                        j = prev
                stack.append((owner[j], j))

    for i in sorted(cands):
        augment(i)
    for j, i in sorted(owner.items(), key=lambda kv: kv[1]):
        used_l.add(i)
        used_r.add(j)
        matched.append((left[i], right[j], "amount+date"))

    unmatched_l = [t for i, t in enumerate(left) if i not in used_l]
    unmatched_r = [t for j, t in enumerate(right) if j not in used_r]
    return {
        "matched": matched,
        "amount_mismatch": mismatched,
        "unmatched_left": unmatched_l,
        "unmatched_right": unmatched_r,
        "summary": {
            "left_rows": len(left),
            "right_rows": len(right),
            "matched": len(matched),
            "amount_mismatch": len(mismatched),
            "unmatched_left": len(unmatched_l),
            "unmatched_right": len(unmatched_r),
            "left_total": str(sum((t.amount for t in left), Decimal(0))),
            "right_total": str(sum((t.amount for t in right), Decimal(0))),
            "difference": str(sum((t.amount for t in left), Decimal(0)) - sum((t.amount for t in right), Decimal(0))),
        },
    }


def rows_for_csv(result: dict) -> list[dict[str, str]]:
    def d(t: Txn | None) -> list[str]:
        return [str(t.row), str(t.amount), str(t.day or ""), t.ref] if t else ["", "", "", ""]

    rows = []
    for lt, r, how in result["matched"]:
        rows.append(["matched:" + how, *d(lt), *d(r)])
    for lt, r in result["amount_mismatch"]:
        rows.append(["amount_mismatch", *d(lt), *d(r)])
    for lt in result["unmatched_left"]:
        rows.append(["unmatched_left", *d(lt), *d(None)])
    for r in result["unmatched_right"]:
        rows.append(["unmatched_right", *d(None), *d(r)])
    head = ["status", "left_row", "left_amount", "left_date", "left_ref", "right_row", "right_amount", "right_date", "right_ref"]
    return [dict(zip(head, row)) for row in rows]


def _self_test() -> None:
    def t(side: str, row: int, amt: str, day: str, ref: str = "") -> Txn:
        return Txn(side, row, Decimal(amt), date.fromisoformat(day), ref, {})

    left = [
        t("L", 2, "100.00", "2026-11-01", "ord_1"),
        t("L", 3, "250.00", "2026-11-02", "ord_2"),
        t("L", 4, "75.50", "2026-11-03"),
        t("L", 5, "75.50", "2026-11-03"),
        t("L", 6, "999.00", "2026-11-05", "ord_9"),
    ]
    right = [
        t("R", 2, "100.00", "2026-11-03", "ord_1"),
        t("R", 3, "249.00", "2026-11-02", "ord_2"),      # reference match, amount differs
        t("R", 4, "75.50", "2026-11-04"),                # amount + date
        t("R", 5, "75.50", "2026-11-09"),                # outside the 2-day window
        t("R", 6, "12.00", "2026-11-05"),
    ]
    res = reconcile(left, right, Decimal(0), days=2)
    s = res["summary"]
    assert s["matched"] == 2 and s["amount_mismatch"] == 1, s
    assert s["unmatched_left"] == 2 and s["unmatched_right"] == 2, s
    assert {x.row for x in res["unmatched_left"]} == {5, 6}
    assert Decimal(s["difference"]) == Decimal("1500.00") - Decimal("512.00"), s["difference"]
    assert parse_amount("(1,234.50)") == Decimal("-1234.50") and parse_amount("₹ 99") == Decimal("99")
    assert parse_day("2026-11-03T10:00:00Z", None) == date(2026, 11, 3)
    assert parse_day("2026-11-03T22:30:00-05:00", None) == date(2026, 11, 4)  # converted to UTC
    for amb in ["05/11/2026", "11-05-2026"]:
        try:
            parse_day(amb, None)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{amb} must need --date-format")
    for bad in ["1,50", "1.234,56"]:
        try:
            parse_amount(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} must be rejected")
    # optimal pairing: greedy file order would match only one pair here
    g = reconcile([t("L", 2, "10", "2026-11-03"), t("L", 3, "10", "2026-11-05")],
                  [t("R", 2, "10", "2026-11-04"), t("R", 3, "10", "2026-11-01")], Decimal(0), 2)
    assert g["summary"]["matched"] == 2, g["summary"]
    tol = reconcile([t("L", 2, "10.00", "2026-11-01")], [t("R", 2, "10.01", "2026-11-01")], Decimal("0.01"), 0)
    assert tol["summary"]["matched"] == 1
    print("recon self-test passed")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reconcile a ledger against a provider/bank export")
    ap.add_argument("left", nargs="?", help="Your ledger CSV")
    ap.add_argument("right", nargs="?", help="Provider or bank CSV")
    for side in ("left", "right"):
        ap.add_argument(f"--{side}-amount", default="amount")
        ap.add_argument(f"--{side}-date")
        ap.add_argument(f"--{side}-ref")
        ap.add_argument(f"--{side}-scale", default="1", help="Multiply amounts, e.g. 0.01 for cents, -1 to flip sign")
    ap.add_argument("--date-format", help="strptime format if dates are not auto-detected")
    ap.add_argument("--days", type=int, default=0, help="Max days apart for amount+date matches")
    ap.add_argument("--amount-tolerance", default="0", help="Max absolute difference to still match")
    ap.add_argument("--out", help="Write a row-level report CSV here")
    ap.add_argument("--json", action="store_true", help="Print the summary as JSON")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        _self_test()
        return 0
    if not (a.left and a.right):
        ap.error("left and right CSV files are required (or use --self-test)")
    try:
        left = load(a.left, "L", a.left_amount, a.left_date, a.left_ref, a.date_format, Decimal(a.left_scale))
        right = load(a.right, "R", a.right_amount, a.right_date, a.right_ref, a.date_format, Decimal(a.right_scale))
        res = reconcile(left, right, Decimal(a.amount_tolerance), a.days)
    except (OSError, ValueError, InvalidOperation) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if a.out:
        rows = rows_for_csv(res)
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["status"])
            w.writeheader()
            w.writerows(rows)
    if a.json:
        print(json.dumps(res["summary"], indent=2))
    else:
        for k, v in res["summary"].items():
            print(f"{k:<16}{v}")
        if a.out:
            print(f"\nrow-level report written to {a.out}")
    unresolved = res["summary"]["amount_mismatch"] + res["summary"]["unmatched_left"] + res["summary"]["unmatched_right"]
    return 3 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
