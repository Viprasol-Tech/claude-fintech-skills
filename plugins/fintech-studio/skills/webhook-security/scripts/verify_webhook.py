#!/usr/bin/env python3
"""Verify or generate Stripe and Razorpay webhook signatures locally.

Part of claude-fintech-skills by Viprasol Tech Private Limited.

Use it to debug "signature verification failed" without guessing: give it the
exact raw body, the header value and the secret. Standard library only.
Run ``python verify_webhook.py --self-test`` to check it.

  python verify_webhook.py stripe  --body body.json --header "t=...,v1=..." --secret whsec_...
  python verify_webhook.py razorpay --body body.json --header <X-Razorpay-Signature> --secret <webhook secret>
  python verify_webhook.py stripe  --body body.json --secret whsec_test --sign     # make a test header

Never paste live secrets into shared logs or chats. Prefer test-mode secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import sys
import time

DEFAULT_TOLERANCE = 300  # seconds; Stripe's official libraries default to 5 minutes


def stripe_sign(body: bytes, secret: str, timestamp: int) -> str:
    signed = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


def stripe_verify(body: bytes, header: str, secret: str, tolerance: int = DEFAULT_TOLERANCE,
                  now: int | None = None) -> tuple[bool, str]:
    """Check a Stripe-Signature header: t=<ts>,v1=<sig>[,v1=...]. Other schemes are ignored."""
    ts, v1 = None, []
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        if key == "t":
            ts = value
        elif key == "v1":
            v1.append(value)
    if ts is None or not (ts.isascii() and ts.isdigit()):
        return False, "no valid t= timestamp in header"
    if not v1:
        return False, "no v1= signature in header (v0 and other schemes are not accepted)"
    expected = stripe_sign(body, secret, int(ts))
    # Compare bytes: compare_digest raises TypeError on non-ASCII str input,
    # which an attacker controls - that would turn a bad request into a 500.
    if not any(hmac.compare_digest(expected.encode(), sig.encode("utf-8", "replace")) for sig in v1):
        return False, ("signature mismatch: wrong secret (test vs live, CLI vs Dashboard), "
                       "or the body was parsed/re-serialised before verification")
    age = (now if now is not None else int(time.time())) - int(ts)
    if tolerance > 0 and abs(age) > tolerance:
        return False, f"timestamp is {age}s old, outside the {tolerance}s tolerance (replay protection)"
    return True, "valid"


def razorpay_sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def razorpay_verify(body: bytes, header: str, secret: str) -> tuple[bool, str]:
    if hmac.compare_digest(razorpay_sign(body, secret).encode(), header.strip().encode("utf-8", "replace")):
        return True, "valid"
    return False, "signature mismatch: wrong webhook secret, or the raw body was modified before verification"


def razorpay_payment_signature(order_id: str, payment_id: str, key_secret: str) -> str:
    """Checkout callback signature: HMAC-SHA256(order_id + '|' + payment_id, key_secret)."""
    return hmac.new(key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def _self_test() -> None:
    body = b'{"id":"evt_1","type":"payment_intent.succeeded"}'
    ts = 1_700_000_000
    sig = stripe_sign(body, "whsec_test", ts)
    ok, _ = stripe_verify(body, f"t={ts},v1={sig}", "whsec_test", now=ts + 10)
    assert ok
    ok, msg = stripe_verify(body, f"t={ts},v1={sig}", "whsec_test", now=ts + 1000)
    assert not ok and "tolerance" in msg
    ok, _ = stripe_verify(body + b" ", f"t={ts},v1={sig}", "whsec_test", now=ts)
    assert not ok, "a modified body must fail"
    ok, _ = stripe_verify(body, f"t={ts},v1=deadbeef,v1={sig},v0=abc", "whsec_test", now=ts)
    assert ok, "any matching v1 passes while secrets roll"
    ok, msg = stripe_verify(body, f"t={ts},v0={sig}", "whsec_test", now=ts)
    assert not ok and "v1" in msg, "v0 must never be accepted"
    assert not stripe_verify(body, f"t={ts},v1=é", "whsec_test", now=ts)[0]   # non-ASCII: no crash
    assert not stripe_verify(body, f"t=²,v1={sig}", "whsec_test", now=ts)[0]   # superscript digit
    assert not razorpay_verify(body, "é", "rzp_secret")[0]
    rz = razorpay_sign(body, "rzp_secret")
    assert razorpay_verify(body, rz, "rzp_secret")[0] and not razorpay_verify(body, rz, "other")[0]
    p = razorpay_payment_signature("order_abc", "pay_xyz", "key_secret")
    assert p == hmac.new(b"key_secret", b"order_abc|pay_xyz", hashlib.sha256).hexdigest()
    print("verify_webhook self-test passed")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify or generate webhook signatures")
    ap.add_argument("provider", nargs="?", choices=["stripe", "razorpay"])
    ap.add_argument("--body", help="File containing the exact raw request body")
    ap.add_argument("--header", help="Stripe-Signature or X-Razorpay-Signature header value")
    ap.add_argument("--secret", help="Webhook signing secret (use a test secret)")
    ap.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE)
    ap.add_argument("--sign", action="store_true", help="Print a valid header for this body instead")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        _self_test()
        return 0
    if not (a.provider and a.body and a.secret):
        ap.error("provider, --body and --secret are required (or use --self-test)")
    with open(a.body, "rb") as fh:
        body = fh.read()
    if a.sign:
        if a.provider == "stripe":
            ts = int(time.time())
            print(f"t={ts},v1={stripe_sign(body, a.secret, ts)}")
        else:
            print(razorpay_sign(body, a.secret))
        return 0
    if not a.header:
        ap.error("--header is required to verify")
    ok, msg = (stripe_verify(body, a.header, a.secret, a.tolerance) if a.provider == "stripe"
               else razorpay_verify(body, a.header, a.secret))
    print(("OK: " if ok else "FAIL: ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
