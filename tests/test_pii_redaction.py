"""Tests for the PII redaction utility."""

from src.security.pii_redaction import redact


def test_redact_email_present() -> None:
    text = "Please contact jane.doe@example.com for support."
    assert redact(text) == "Please contact [EMAIL_REDACTED] for support."


def test_redact_phone_present() -> None:
    text = "Call me at +1 (415) 555-2671 when available."
    assert redact(text) == "Call me at [PHONE_REDACTED] when available."


def test_redact_both_present() -> None:
    text = "Reach john@corp.io or +44 20 7946 0958 for incident updates."
    assert redact(text) == "Reach [EMAIL_REDACTED] or [PHONE_REDACTED] for incident updates."


def test_redact_neither_present() -> None:
    text = "The VPN issue started after reboot and affects only office wifi."
    assert redact(text) == text
