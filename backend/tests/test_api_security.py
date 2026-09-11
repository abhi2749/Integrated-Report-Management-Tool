from api_security import public_exception_message, sanitize_error_message


def test_sanitizes_password_material():
    result = sanitize_error_message("connection failed password=super-secret")
    assert "super-secret" not in result
    assert "[redacted]" in result


def test_sanitizes_connection_uri():
    result = public_exception_message(
        RuntimeError("failed mysql://admin:super-secret@db.example:3306/reporting"),
        "Database operation failed.",
    )
    assert "super-secret" not in result
    assert "mysql://" not in result


def test_bounded_error_output():
    result = sanitize_error_message("x" * 5000)
    assert len(result) == 1000
