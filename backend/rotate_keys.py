"""Safe application key rotation CLI."""
from __future__ import annotations

import argparse

from auth import validate_auth_configuration
from connection_registry import rotate_encrypted_passwords
from key_manager import ensure_keys, rollback, rotate
from security import get_fernet, get_previous_fernet


def rotate_encryption() -> int:
    ensure_keys()
    rotate("encryption")
    try:
        get_fernet()
        get_previous_fernet()
        result = rotate_encrypted_passwords()
    except Exception:
        rollback("encryption")
        raise
    print(
        f"Encryption rotation complete: {result['rotated_passwords']} stored passwords "
        f"rotated across {result['total_connections']} connections."
    )
    print("Previous encryption key retained in the persistent keyring for recovery.")
    return 0


def rotate_secret() -> int:
    ensure_keys()
    rotate("secret")
    validate_auth_configuration()
    print("Application signing-key rotation complete. Existing tokens remain verifiable during the transition window.")
    print("Previous signing key retained in the persistent keyring for recovery.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rotate Reporting Tool application keys safely.")
    parser.add_argument("--encryption", action="store_true", help="Rotate the encryption key and re-encrypt saved connection passwords.")
    parser.add_argument("--secret", action="store_true", help="Rotate the authentication signing key.")
    parser.add_argument("--all", action="store_true", help="Rotate both application keys.")
    args = parser.parse_args(argv)
    if not (args.encryption or args.secret or args.all):
        parser.error("Specify --encryption, --secret, or --all.")
    if args.encryption or args.all:
        rotate_encryption()
    if args.secret or args.all:
        rotate_secret()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
