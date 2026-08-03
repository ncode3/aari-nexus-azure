from app.services.audit import _redact


def test_audit_redacts_sensitive_values() -> None:
    result = _redact({"token": "secret-value", "status": "ok", "document_content": "private"})
    assert result == {
        "token": "[REDACTED]",
        "status": "ok",
        "document_content": "[REDACTED]",
    }

