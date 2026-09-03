"""Utilities for removing basic PII from free-form text."""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Covers common US formats and many international representations.
PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{3,4}(?!\w)"
)


def redact(text: str) -> str:
    """Replace email addresses and phone numbers with redaction tokens."""
    redacted = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
    redacted = PHONE_PATTERN.sub("[PHONE_REDACTED]", redacted)
    return redacted
