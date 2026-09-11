import logging

from api_security import public_exception_message
from logging_config import JsonFormatter, audit_event


def test_public_exception_message_redacts_credentials():
    exc = RuntimeError("connection failed password=SuperSecret mysql://user:pass@example/db")
    message = public_exception_message(exc, "Request failed.")
    assert "SuperSecret" not in message
    assert "mysql://" not in message


def test_json_formatter_redacts_exception_traceback():
    try:
        raise RuntimeError("password=SuperSecret")
    except RuntimeError:
        record = logging.LogRecord("reporting", logging.ERROR, __file__, 1, "request failed", (), None)
        record.exc_info = __import__("sys").exc_info()
        output = JsonFormatter().format(record)
        assert "SuperSecret" not in output
        assert "RuntimeError" in output


def test_audit_secret_fields_are_redacted():
    # Ensure the audit helper remains callable with secret-like nested data.
    audit_event("test_observability", password="SuperSecret", nested={"token": "abc"})
