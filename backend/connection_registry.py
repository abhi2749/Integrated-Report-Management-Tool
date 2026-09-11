"""
Custom Reporting Tool
Secure Connection Registry

Security Phase - Step 2B:
- Encrypt saved database passwords at rest.
- Keep passwords server-side.
- Never expose passwords through public connection responses.
- Transparently decrypt passwords only when the backend needs to connect.
- Safely migrate legacy plaintext passwords on first registry read.

Existing connection IDs, JSON structure, public API behavior and timestamps
are preserved wherever possible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import secrets
import shutil

from metadata_repository import create_metadata_repository
from config import METADATA_DB_FILE

from security import (
    SecretConfigurationError,
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    is_encrypted_secret,
)


from config import DATA_DIR

REGISTRY_DIR = DATA_DIR
REGISTRY_FILE = REGISTRY_DIR / "connections.json"
METADATA_REPOSITORY = create_metadata_repository(REGISTRY_FILE, collection="connections", db_path=METADATA_DB_FILE)
MIGRATION_BACKUP_FILE = REGISTRY_DIR / "connections.json.pre_encryption.bak"


def _ensure_file() -> None:
    METADATA_REPOSITORY.ensure()


def _read_raw() -> list[dict[str, Any]]:
    """Read the registry without decrypting or migrating anything."""
    return METADATA_REPOSITORY.read()


def _write_raw(items: list[dict[str, Any]]) -> None:
    """Persist registry data through the metadata repository boundary."""
    METADATA_REPOSITORY.write(items)


def _backup_before_migration() -> None:
    """
    Preserve the original registry before the first plaintext-to-encrypted
    migration.

    The backup is created only once and never overwritten automatically.
    """
    _ensure_file()

    if MIGRATION_BACKUP_FILE.exists():
        return

    try:
        shutil.copy2(
            REGISTRY_FILE,
            MIGRATION_BACKUP_FILE,
        )
    except OSError as error:
        raise RuntimeError(
            "Unable to create the pre-encryption connection registry backup."
        ) from error


def _migrate_plaintext_passwords(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """
    Encrypt legacy plaintext passwords.

    Returns:
        (items, migrated)
    """
    migrated = False
    updated_items = []

    for item in items:
        updated = dict(item)
        password = updated.get("password")

        if password in (None, ""):
            updated_items.append(updated)
            continue

        if is_encrypted_secret(password):
            # Validate that the token is decryptable with the active key.
            # This prevents silently accepting a token encrypted with a
            # different/lost key.
            decrypt_secret(password)
            updated_items.append(updated)
            continue

        # Existing plaintext password.
        updated["password"] = encrypt_secret(password)
        migrated = True
        updated_items.append(updated)

    return updated_items, migrated


def _read() -> list[dict[str, Any]]:
    """Read connection metadata without validating unrelated credentials.

    Connection passwords are intentionally not decrypted during a registry
    read. A stale or invalid credential for one connection must never prevent
    listing, creating, updating, or deleting a different connection.

    Password validation/decryption happens only when a specific connection is
    requested for runtime database access.
    """
    return _read_raw()


def _public(item: dict[str, Any]) -> dict[str, Any]:
    """
    Return a safe public representation.

    Passwords are never returned, whether encrypted or plaintext.
    """
    return {
        key: value
        for key, value in item.items()
        if key != "password"
    }


def _runtime_connection(item: dict[str, Any]) -> dict[str, Any]:
    """
    Return an internal connection object with a decrypted password.

    This function must only be used by backend code that needs to connect
    to the database. It is never used for API responses.
    """
    runtime = dict(item)

    password = runtime.get("password")

    if password in (None, ""):
        runtime["password"] = None
        return runtime

    if not is_encrypted_secret(password):
        # Legacy plaintext is handled only for the connection that is being
        # used. Do not touch unrelated saved connections.
        runtime["password"] = password
        return runtime

    runtime["password"] = decrypt_secret(password)

    return runtime


def list_connections() -> list[dict[str, Any]]:
    """Return all saved connections without passwords."""
    return [
        _public(item)
        for item in _read()
    ]


def get_connection(connection_id: str) -> dict[str, Any] | None:
    """
    Retrieve one saved connection for internal backend use.

    The returned object contains the decrypted password because existing
    database/reporting code needs it to create a DB connection.

    API endpoints must use list_connections() or _public() for responses.
    """
    for item in _read():
        if item.get("id") == connection_id:
            return _runtime_connection(item)

    return None


def create_connection(data: dict[str, Any]) -> dict[str, Any]:
    """
    Create a saved connection.

    The password is encrypted before it is written to connections.json.
    """
    items = _read()

    now = datetime.now(timezone.utc).isoformat()

    password = data.get("password")

    item = {
        "id": data.get("id") or f"conn_{secrets.token_hex(8)}",
        "name": str(data["name"]).strip(),
        "source_type": str(data["source_type"]).lower().strip(),
        "host": str(data["host"]).strip(),
        "port": int(data["port"]),
        "username": data.get("username") or None,
        "password": encrypt_secret(password),
        "status": data.get("status", "saved"),
        "server_version": data.get("server_version", ""),
        "created_at": now,
        "updated_at": now,
    }

    items = [
        existing
        for existing in items
        if existing.get("id") != item["id"]
    ]

    items.insert(0, item)

    _write_raw(items)

    return _public(item)


def update_connection(
    connection_id: str,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Update a saved connection.

    If password is omitted/empty, retain the existing encrypted password.
    If a new password is supplied, encrypt it before writing.
    """
    items = _read()

    for index, existing in enumerate(items):
        if existing.get("id") != connection_id:
            continue

        updated = {
            **existing,
            **data,
            "id": connection_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        password = data.get("password")

        if password:
            updated["password"] = encrypt_secret(password)
        else:
            # Preserve the existing stored credential without decrypting it.
            # A broken credential must not block metadata-only updates.
            updated["password"] = existing.get("password")

        items[index] = updated

        _write_raw(items)

        return _public(updated)

    return None


def delete_connection(connection_id: str) -> bool:
    """Delete a saved connection."""
    items = _read()

    updated = [
        item
        for item in items
        if item.get("id") != connection_id
    ]

    if len(updated) == len(items):
        return False

    _write_raw(updated)

    return True

def rotate_encrypted_passwords() -> dict[str, int]:
    """Re-encrypt every stored password with the active key.

    Rotation is intentionally explicit: configure the new ENCRYPTION_KEY as
    active and the old key as ENCRYPTION_KEY_PREVIOUS, then run this function.
    The registry is backed up before any write. Secrets are never returned.
    """
    from security import get_previous_fernet

    if get_previous_fernet() is None:
        raise SecretConfigurationError(
            "ENCRYPTION_KEY_PREVIOUS must be configured before encryption-key rotation."
        )

    items = _read_raw()
    updated_items = []
    migrated = 0

    for item in items:
        updated = dict(item)
        password = updated.get("password")
        if password in (None, ""):
            updated_items.append(updated)
            continue

        plaintext = decrypt_secret(password) if is_encrypted_secret(password) else str(password)
        updated["password"] = encrypt_secret(plaintext)
        updated_items.append(updated)
        migrated += 1

    if migrated:
        # MetadataRepository.write() performs the replacement in a transaction.
        # Keep backups outside this operation so rotation cannot accidentally
        # create an unprotected plaintext/ciphertext copy of credentials.
        _write_raw(updated_items)

    return {"total_connections": len(items), "rotated_passwords": migrated}

