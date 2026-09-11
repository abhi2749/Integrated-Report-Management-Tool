from pathlib import Path

from startup_validation import validate_environment


def test_production_environment_validation_allows_automatic_secret_material():
    result = validate_environment({
        "APP_ENV": "production",
        "CORS_ORIGINS": "https://example.test",
    })
    assert result["ok"] is True
    assert not any("SECRET_KEY" in error or "ENCRYPTION_KEY" in error for error in result["errors"])


def test_production_environment_validation_accepts_safe_configuration():
    result = validate_environment({
        "APP_ENV": "production",
        "SECRET_KEY": "s" * 32,
        "ENCRYPTION_KEY": __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode(),
        "CORS_ORIGINS": "https://reports.example.test",
        "CORS_ALLOW_CREDENTIALS": "true",
        "SECURE_COOKIES": "true",
        "APP_DEBUG": "false",
    })
    assert result["ok"] is True
    assert result["errors"] == []


def test_backend_runbook_is_present():
    assert Path(__file__).resolve().parents[1].joinpath("PRODUCTION_RUNBOOK.md").is_file()
