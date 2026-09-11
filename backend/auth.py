"""
Custom Reporting Tool
Security Phase - Step 3A/3D Authentication Foundation

Password hashing:
    PBKDF2-HMAC-SHA256

Authentication tokens:
    Signed HMAC-SHA256 tokens with expiration.

ENCRYPTION_KEY remains separate and is handled by security.py.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any


from auth_session_registry import is_token_revoked
from key_manager import ensure_keys, get_key, get_previous_key

ensure_keys()


class AuthenticationConfigurationError(RuntimeError):
    pass


class AuthenticationTokenError(RuntimeError):
    pass


PBKDF2_ITERATIONS = int(
    os.getenv("AUTH_PBKDF2_ITERATIONS", "600000")
)

TOKEN_EXPIRE_SECONDS = int(
    os.getenv("AUTH_TOKEN_EXPIRE_SECONDS", "3600")
)

AUTH_ALGORITHM = "HS256"


def _get_secret_key() -> bytes:
    try:
        return get_key("SECRET_KEY").encode("utf-8")
    except (RuntimeError, ValueError) as exc:
        raise AuthenticationConfigurationError(
            "SECRET_KEY is not available from the persistent key lifecycle."
        ) from exc


def _get_previous_secret_key() -> bytes | None:
    secret = get_previous_key("SECRET_KEY_PREVIOUS")
    return secret.encode("utf-8") if secret else None


def _verify_signature(message: bytes, signature: str) -> bool:
    keys = [_get_secret_key()]
    previous = _get_previous_secret_key()
    if previous is not None:
        keys.append(previous)
    return any(
        hmac.compare_digest(
            signature,
            _base64url_encode(hmac.new(key, message, hashlib.sha256).digest()),
        )
        for key in keys
    )


def generate_secret_key() -> str:
    """Generate a high-entropy application signing key for secure storage."""
    return secrets.token_urlsafe(48)


def validate_auth_configuration() -> None:
    if PBKDF2_ITERATIONS < 100000:
        raise AuthenticationConfigurationError(
            "AUTH_PBKDF2_ITERATIONS must be at least 100000."
        )

    if TOKEN_EXPIRE_SECONDS <= 0:
        raise AuthenticationConfigurationError(
            "AUTH_TOKEN_EXPIRE_SECONDS must be greater than zero."
        )

    _get_secret_key()


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Password cannot be empty.")

    if len(password) > 1024:
        raise ValueError("Password is too long.")

    salt = secrets.token_bytes(16)

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )

    salt_text = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    hash_text = base64.urlsafe_b64encode(derived).decode("ascii").rstrip("=")

    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_text}${hash_text}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False

    try:
        algorithm, iterations_text, salt_text, hash_text = stored_hash.split("$", 3)

        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iterations_text)

        if iterations < 100000:
            return False

        salt = base64.urlsafe_b64decode(
            salt_text + "=" * (-len(salt_text) % 4)
        )
        expected_hash = base64.urlsafe_b64decode(
            hash_text + "=" * (-len(hash_text) % 4)
        )

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )

        return hmac.compare_digest(actual_hash, expected_hash)

    except (ValueError, TypeError, UnicodeDecodeError):
        return False


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(
        value + "=" * (-len(value) % 4)
    )


def _sign(message: bytes) -> str:
    return _base64url_encode(
        hmac.new(
            _get_secret_key(),
            message,
            hashlib.sha256,
        ).digest()
    )


def revoke_access_token(token: str, expires_at: int) -> None:
    from auth_session_registry import revoke_token
    revoke_token(token, expires_at)


def is_access_token_revoked(token: str) -> bool:
    return is_token_revoked(token)


def create_access_token(
    user_id: str,
    username: str,
    role: str = "report_user",
    expires_in: int | None = None,
) -> str:
    if not user_id:
        raise ValueError("user_id is required.")

    if not username:
        raise ValueError("username is required.")

    if not role:
        raise ValueError("role is required.")

    expiry = (
        TOKEN_EXPIRE_SECONDS
        if expires_in is None
        else int(expires_in)
    )

    if expiry <= 0:
        raise ValueError("expires_in must be greater than zero.")

    now = int(time.time())

    header = {
        "alg": AUTH_ALGORITHM,
        "typ": "JWT",
    }

    payload = {
        "sub": str(user_id),
        "jti": secrets.token_urlsafe(24),
        "username": str(username),
        "role": str(role),
        "iat": now,
        "exp": now + expiry,
    }

    header_text = _base64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_text = _base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    signing_input = f"{header_text}.{payload_text}".encode("ascii")
    signature = _sign(signing_input)

    return f"{header_text}.{payload_text}.{signature}"


def verify_access_token(token: str) -> dict[str, Any]:
    if not isinstance(token, str) or not token:
        raise AuthenticationTokenError("Authentication token is required.")

    if is_access_token_revoked(token):
        raise AuthenticationTokenError(
            "Authentication token has been revoked."
        )

    parts = token.split(".")

    if len(parts) != 3:
        raise AuthenticationTokenError("Invalid authentication token.")

    header_text, payload_text, signature = parts
    signing_input = f"{header_text}.{payload_text}".encode("ascii")

    if not _verify_signature(signing_input, signature):
        raise AuthenticationTokenError("Invalid authentication token.")

    try:
        header = json.loads(_base64url_decode(header_text).decode("utf-8"))
        payload = json.loads(_base64url_decode(payload_text).decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthenticationTokenError(
            "Invalid authentication token."
        ) from exc

    if header.get("alg") != AUTH_ALGORITHM or header.get("typ") != "JWT":
        raise AuthenticationTokenError("Invalid authentication token.")

    try:
        expiry = int(payload["exp"])
        user_id = str(payload["sub"])
        username = str(payload["username"])
        role = str(payload["role"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationTokenError(
            "Invalid authentication token claims."
        ) from exc

    if int(time.time()) >= expiry:
        raise AuthenticationTokenError("Authentication token has expired.")

    return {
        "user_id": user_id,
        "username": username,
        "role": role,
        "issued_at": int(payload.get("iat", 0)),
        "expires_at": expiry,
    }


def safe_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "permissions": user.get("permissions"),
        "active": bool(user.get("active", True)),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }
