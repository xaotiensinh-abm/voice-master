"""Author tool — issue a License Key for a customer's machine code.

  python tools/license_gen.py --machine-code XXXX-XXXX-XXXX-XXXX [--exp 2027-06-26] [--tier std]

Uses tools/keys/private.pem (created by license_keygen.py). The printed key is
bound to that machine code and verifies against the public key embedded in the app.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from cryptography.hazmat.primitives import serialization

# Make backend importable for the crypto core.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from services.license_core import encode_key, make_payload  # noqa: E402

PRIV_PATH = Path(__file__).resolve().parent / "keys" / "private.pem"


def main() -> int:
    ap = argparse.ArgumentParser(description="Issue a Voice-Master license key.")
    ap.add_argument("--machine-code", required=True, help="Customer machine code (XXXX-XXXX-XXXX-XXXX)")
    ap.add_argument("--exp", default=None, help="Expiry YYYY-MM-DD (omit = perpetual)")
    ap.add_argument("--tier", default="std")
    args = ap.parse_args()

    if not PRIV_PATH.exists():
        print(f"ERROR: private key not found at {PRIV_PATH}. Run tools/license_keygen.py first.")
        return 1

    priv = serialization.load_pem_private_key(PRIV_PATH.read_bytes(), password=None)
    mc = args.machine_code.strip().upper()
    payload = make_payload(mc, exp=args.exp, tier=args.tier)
    key = encode_key(payload, priv)  # type: ignore[arg-type]

    print(f"Machine code : {mc}")
    print(f"Expiry       : {args.exp or 'perpetual'}")
    print(f"Tier         : {args.tier}")
    print()
    print("License Key (gửi cho khách / paste vào app):")
    print(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
