from pathlib import Path
from startup_validation import validate_backend_layout, validate_environment, validate_runtime


def test_backend_layout_is_complete():
    result = validate_backend_layout(Path(__file__).resolve().parents[1])
    assert result["ok"] is True
    assert result["missing_files"] == []


def test_development_environment_does_not_require_production_secrets():
    result = validate_environment({"APP_ENV": "development"})
    assert result["ok"] is True
    assert result["errors"] == []


def test_production_without_manual_secret_keys_is_valid_for_automatic_key_lifecycle():
    result = validate_environment({"APP_ENV": "production", "CORS_ORIGINS": "https://example.test"})
    assert result["ok"] is True
    assert not any("SECRET_KEY" in item or "ENCRYPTION_KEY" in item for item in result["errors"])


def test_production_with_explicit_required_secrets_is_valid():
    from cryptography.fernet import Fernet

    result = validate_environment({"APP_ENV": "production", "SECRET_KEY": "s" * 32, "ENCRYPTION_KEY": Fernet.generate_key().decode(), "CORS_ORIGINS": "https://example.test"})
    assert result["ok"] is True
    assert result["errors"] == []


def test_runtime_validation_combines_layout_and_environment():
    result = validate_runtime(Path(__file__).resolve().parents[1], {"APP_ENV": "development", "CORS_ORIGINS": "http://localhost:5173"})
    assert result["ok"] is True
    assert result["layout"]["ok"] is True
    assert result["environment"]["ok"] is True


def test_production_rejects_debug_mode():
    result = validate_environment({"APP_ENV": "production", "SECRET_KEY": "s" * 32, "ENCRYPTION_KEY": "x", "APP_DEBUG": "true"})
    assert result["ok"] is False
    assert any("APP_DEBUG" in item for item in result["errors"])


def test_production_rejects_wildcard_cors_with_credentials():
    result = validate_environment({"APP_ENV": "production", "SECRET_KEY": "s" * 32, "ENCRYPTION_KEY": "x", "CORS_ORIGINS": "*", "CORS_ALLOW_CREDENTIALS": "true"})
    assert result["ok"] is False
    assert any("Wildcard CORS" in item for item in result["errors"])


def test_production_requires_secure_cookies():
    result = validate_environment({"APP_ENV": "production", "SECRET_KEY": "s" * 32, "ENCRYPTION_KEY": "x", "CORS_ORIGINS": "https://example.test", "SECURE_COOKIES": "false"})
    assert result["ok"] is False
    assert any("SECURE_COOKIES" in item for item in result["errors"])
