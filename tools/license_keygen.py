"""Author tool — generate the Ed25519 keypair ONCE.

  python tools/license_keygen.py

Writes the PRIVATE key to tools/keys/private.pem (gitignored — KEEP SECRET) and
prints the PUBLIC key (raw, base64url) to paste into
backend/services/license_core.py as PUBLIC_KEY_B64.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

KEYS_DIR = Path(__file__).resolve().parent / "keys"
PRIV_PATH = KEYS_DIR / "private.pem"


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _print_public(priv: Ed25519PrivateKey) -> None:
    pub_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    print()
    print("Paste into backend/services/license_core.py  ->  PUBLIC_KEY_B64:")
    print()
    print(f'PUBLIC_KEY_B64 = "{b64u(pub_raw)}"')


def main() -> None:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    if PRIV_PATH.exists():
        print(f"Private key already exists: {PRIV_PATH} (not overwriting).")
        priv = serialization.load_pem_private_key(PRIV_PATH.read_bytes(), password=None)
        _print_public(priv)  # type: ignore[arg-type]
        return

    priv = Ed25519PrivateKey.generate()
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    PRIV_PATH.write_bytes(pem)
    os.chmod(PRIV_PATH, 0o600)
    print("Private key written to:", PRIV_PATH, "(KEEP SECRET, never commit)")
    _print_public(priv)


if __name__ == "__main__":
    main()
