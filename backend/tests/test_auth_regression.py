"""
Authentication regression tests.

These tests exercise the existing password/token helpers without changing
the authentication implementation.
"""

import os

import pytest

os.environ.setdefault("SECRET_KEY", "regression-test-secret-key-only")
os.environ.setdefault("ENCRYPTION_KEY", "9T7M5x5vR1p0w8c6y2n4z7a9s3d5f8g0h1j4k6m8p0r2t4v6x8z0=")

from auth import hash_password, verify_password


def test_password_hash_is_not_plaintext():
    password = "Regression-Test-Password-123!"
    hashed = hash_password(password)

    assert hashed != password
    assert isinstance(hashed, str)
    assert len(hashed) > 20


def test_password_verification_accepts_correct_password():
    password = "Regression-Test-Password-123!"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_password_verification_rejects_wrong_password():
    password = "Regression-Test-Password-123!"
    hashed = hash_password(password)

    assert verify_password("Wrong-Password-123!", hashed) is False


def test_different_hashes_are_generated_for_same_password():
    password = "Regression-Test-Password-123!"

    first = hash_password(password)
    second = hash_password(password)

    assert first != second
    assert verify_password(password, first) is True
    assert verify_password(password, second) is True
