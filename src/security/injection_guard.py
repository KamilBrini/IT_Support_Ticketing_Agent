"""Simple pattern-based prompt injection guard."""

from __future__ import annotations

import re

# Intentionally simple and explicit for deterministic behavior.
_SUSPICIOUS_PATTERNS = [
    re.compile(r"\bignore\s+(all\s+)?(the\s+)?previous\s+instructions\b", re.IGNORECASE),
    re.compile(r"\breveal\s+(your\s+)?system\s+prompt\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(all\s+)?(your\s+)?rules\b", re.IGNORECASE),
    re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+dan\b", re.IGNORECASE),
    re.compile(r"\bstay\s+in\s+character\b", re.IGNORECASE),
    re.compile(r"\bprint\s+(out\s+)?(your\s+)?(hidden\s+)?instructions\b", re.IGNORECASE),
    re.compile(r"\boutput\s+(your\s+)?(internal|hidden|developer|system)\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bshow\s+me\s+(the\s+)?(system|developer)\s+prompt\b", re.IGNORECASE),
]


def is_suspicious(text: str) -> bool:
    """Return True when text matches obvious prompt-injection or jailbreak patterns."""
    normalized = text.strip()
    if not normalized:
        return False

    for pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(normalized):
            return True

    return False
